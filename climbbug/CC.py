import json
import os
import time
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

BASE = "https://shogidb2.com"

SAVE_DIR = "data"
URL_FILE = "game_urls.txt"
FAILED_FILE = "failed_urls.txt"

MAX_GAMES = int(os.getenv("MAX_GAMES", "100000"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "5000"))
START_INDEX = int(os.getenv("START_INDEX", "1"))

os.makedirs(SAVE_DIR, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0"
}


def collect_game_urls():
    urls = []

    if os.path.exists(URL_FILE):
        print("已找到 game_urls.txt，直接讀取")
        with open(URL_FILE, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
        return urls[:MAX_GAMES]

    for page in range(1, MAX_PAGES + 1):
        print(f"抓列表 PAGE {page}")

        url = f"{BASE}/newrecords?page={page}"

        try:
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()
        except Exception as e:
            print("列表頁失敗:", e)
            time.sleep(5)
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        page_urls = []

        for a in soup.select('a[href^="/games/"]'):
            href = a.get("href")

            if href and "thumb.svg" not in href:
                full_url = BASE + href
                page_urls.append(full_url)

        page_urls = list(dict.fromkeys(page_urls))

        if not page_urls:
            print("這頁沒有棋局，可能到底了")
            break

        urls.extend(page_urls)
        urls = list(dict.fromkeys(urls))

        print(f"目前累積 {len(urls)} 局")

        with open(URL_FILE, "w", encoding="utf-8") as f:
            for u in urls:
                f.write(u + "\n")

        if len(urls) >= MAX_GAMES:
            break

        time.sleep(1)

    return urls[:MAX_GAMES]


def create_driver():
    options = Options()
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--headless=new")
    options.add_argument("window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(40)

    return driver


def find_game_data_from_logs(driver):
    logs = driver.get_log("performance")

    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
        except:
            continue

        if msg.get("method") != "Network.webSocketFrameReceived":
            continue

        payload = msg["params"]["response"].get("payloadData", "")

        if '"moves"' not in payload or '"csa"' not in payload:
            continue

        try:
            arr = json.loads(payload)
            data = arr[4]["response"]["diff"]["e"][0][1]["data"]
            return data
        except:
            continue

    return None


def build_csa(data):
    lines = []

    lines.append("V2.2")
    lines.append(f"N+{data.get('player1', 'black')}")
    lines.append(f"N-{data.get('player2', 'white')}")

    if data.get("tournament"):
        lines.append(f"$EVENT:{data['tournament']}")
    if data.get("place"):
        lines.append(f"$SITE:{data['place']}")
    if data.get("start_at"):
        lines.append(f"$START_TIME:{data['start_at']}")
    if data.get("end_at"):
        lines.append(f"$END_TIME:{data['end_at']}")
    if data.get("strategy"):
        lines.append(f"$OPENING:{data['strategy']}")

    lines += [
        "P1-KY-KE-GI-KI-OU-KI-GI-KE-KY",
        "P2 * -HI *  *  *  *  * -KA * ",
        "P3-FU-FU-FU-FU-FU-FU-FU-FU-FU",
        "P4 *  *  *  *  *  *  *  *  * ",
        "P5 *  *  *  *  *  *  *  *  * ",
        "P6 *  *  *  *  *  *  *  *  * ",
        "P7+FU+FU+FU+FU+FU+FU+FU+FU+FU",
        "P8 * +KA *  *  *  *  * +HI * ",
        "P9+KY+KE+GI+KI+OU+KI+GI+KE+KY",
        "+",
    ]

    moves = sorted(data.get("moves", []), key=lambda x: x.get("num", 0))

    for m in moves:
        csa = m.get("csa")
        if csa:
            lines.append(csa)

    return "\n".join(lines)


def get_csa(game_url):
    driver = create_driver()

    try:
        try:
            driver.get(game_url)
        except Exception:
            try:
                driver.execute_script("window.stop();")
            except:
                pass

        time.sleep(6)

        # 清掉載入頁面的log
        try:
            driver.get_log("performance")
        except:
            pass

        buttons = driver.find_elements(By.TAG_NAME, "a")

        for b in buttons:
            if "CSA" in b.text.strip():
                driver.execute_script("arguments[0].click();", b)
                break
        else:
            return ""

        time.sleep(2)

        data = find_game_data_from_logs(driver)

        if not data:
            return ""

        return build_csa(data)

    finally:
        driver.quit()


def save_failed(url):
    with open(FAILED_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")


def main():
    urls = collect_game_urls()

    print(f"\n總共準備抓 {len(urls)} 局")

    idx = START_INDEX

    for url in urls:
        if idx > MAX_GAMES:
            print("已達 100000 筆，停止")
            break

        path = os.path.join(SAVE_DIR, f"game{idx}.csa")

        if os.path.exists(path):
            print(f"跳過已存在: game{idx}.csa")
            idx += 1
            continue

        print(f"\n抓 game{idx}:")
        print(url)

        try:
            csa = get_csa(url)

            if not csa or len(csa) < 100:
                print("失敗或內容太短")
                save_failed(url)
                continue

            with open(path, "w", encoding="utf-8-sig", newline="\n") as f:
                f.write(csa)

            print(f"已存 {path}，長度 {len(csa)}")

            idx += 1

        except Exception as e:
            print("發生錯誤:", e)
            save_failed(url)

        time.sleep(1)


if __name__ == "__main__":
    main()
