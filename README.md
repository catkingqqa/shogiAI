shogiAI 小筆記

這個專案把 CSA 將棋棋譜整理成之後可以拿去訓練模型的資料。

流程大概是：

CSA 棋譜 -> 用 cshogi 檢查能不能合法重播 -> 每一步切成一筆樣本 -> 存成 .npz

另外也有準備 Jupyter Notebook，可以直接把棋盤顯示出來，不用只看一堆數字。


先安裝

進到專案資料夾：

cd \shogiAI

裝需要的套件：

python -m pip install -r requirements.txt

主要會用到 cshogi、numpy、jupyter、ipython。


CSA 放哪裡

把棋譜放在 data 裡就好。

例如現在是：

data\game1.csa

如果之後有更多棋譜，也可以像這樣放：

data\game1.csa
data\game2.csa
data\game3.csa


把 CSA 轉成訓練資料

轉一個檔案：

python src\csa_preprocess.py --input data\game1.csa --output out\game1.npz --encoding utf-8 --keep-invalid-report out\game1_invalid.jsonl

這行的意思是：

讀 data\game1.csa。
用 cshogi 檢查每一步是否合法。
每一步下棋前都存成一筆訓練樣本。
最後輸出到 out\game1.npz。
如果有壞掉或不能重播的棋譜，原因會寫到 out\game1_invalid.jsonl。

如果一次要轉整個 data 資料夾：

python src\csa_preprocess.py --input data --output out\samples.npz --recursive --encoding utf-8 --keep-invalid-report out\invalid.jsonl

注意如果你的 game1.csa 是 UTF-8，所以記得加 --encoding utf-8。

成功時大概會看到：

parsed_games: 1
legal_games: 1
invalid_games: 0
samples: 119
output: out\game1.npz

可以這樣看：

parsed_games 是讀到幾局棋。
legal_games 是幾局可以完整合法重播。
invalid_games 是幾局有問題。
samples 是產生幾筆樣本，通常就是手數。
output 是輸出的檔案。

所以 samples: 119 就是這局棋產生了 119 筆訓練資料。


.npz 裡面是什麼

.npz 是 NumPy 的資料檔。它不是拿來直接用 Excel 開的，比較像是給 Python 或模型訓練程式讀的。

裡面有這幾個東西：

states
moves
values
meta
move_label_count


states

states 是棋盤狀態。

形狀是 (N, 43, 9, 9)。

N 是有幾筆樣本。
43 是每個局面用 43 張特徵平面表示。
9 x 9 是將棋盤。

可以想成：每一步下棋前，程式都把棋盤拍成一張模型看得懂的多層圖片。

43 層大概分成自己的盤上棋子、對手的盤上棋子、自己的持駒、對手的持駒、現在輪到誰。

預設會把後手的局面轉過來，所以模型永遠用現在要下的人角度看棋盤。


moves

moves 是下一手。

模型不能直接吃 7g7f 這種文字，所以程式會把每一步轉成一個數字 label。

例如 moves[0] 是某個整數，這個整數就代表那個局面下實戰下出的那一步。


values

values 是勝負結果，但不是單純先手贏或後手贏。

它是從現在輪到下棋的人角度看：

1.0 代表現在這個人最後贏了。
-1.0 代表現在這個人最後輸了。
0.0 代表和棋。

這樣訓練 value head 時會比較直覺。


meta

meta 是給人看的補充資訊。

裡面會記來源是哪個 CSA、第幾手、下棋前的 SFEN、下一手的 USI 表示。

除錯、看資料有沒有切對時很有用。


move_label_count

move_label_count 是 move label 的總數。

目前是 13689。

如果之後做 policy head，輸出大小就可以用這個數字。


Policy + Value Network

若要從 MySQL 棋譜資料訓練 policy + value network，可先輸出資料集：

```powershell
python src\export_policy_dataset.py --output out\policy_dataset.npz --host 140.135.65.53 --port 3306 --user 11211213 --password <password> --database DB11211213
```

再訓練小型 CNN：

```powershell
python src\train_policy.py --input out\policy_dataset.npz --output out\policy_model.pt --batch-size 256 --value-loss-weight 0.25
```

啟動瀏覽器 API 時若 `out\policy_model.pt` 存在，AI 對弈頁面會自動顯示 policy 候選手與 value 估計；alpha-beta 搜尋會用 policy 分數做走法排序。

若要讓 alpha-beta 的根節點候選手使用 value head 加分，可在啟動時加上：

```powershell
--value-weight 200
```

加速選項：
```powershell
--policy-order-ply 1
```

`--policy-order-ply` 控制 alpha-beta 搜尋前幾層使用 policy network 排序。`2` 是預設值；若 CPU 推論太慢，可改成 `1`，只在根節點附近用 policy，深層改用傳統 tactical / killer / history 排序。`0` 代表搜尋內完全不使用 policy 排序，但候選手顯示仍可單獨使用 policy。

`--value-weight 0` 代表關閉 value 加分。建議先從 `100` 或 `200` 測起，避免 value head 蓋過手工評估；目前 value 只用在根節點候選手加分，比在所有葉節點都跑 CNN 快很多。


想看 .npz 內容

可以用 Python 簡單印一下：

import json
import numpy as np

data = np.load("out/game1.npz")

print(data.files)
print(data["states"].shape)
print(data["moves"][:10])
print(data["values"][:10])
print(json.loads(str(data["meta"][0])))


用 Jupyter 看棋盤

先開 Jupyter：

jupyter notebook


NNUE-like Value Evaluator

本專案也提供第一階段 NNUE-like 評估器。它不使用整盤 CNN，而是把盤面轉成以雙方玉位置為 anchor 的稀疏特徵，再用 `EmbeddingBag` 訓練 value evaluator。這比較接近專業將棋引擎常用的 NNUE 思路，也比較適合之後接到 alpha-beta 搜尋。

```powershell
python src\train_nnue.py --input out\policy_dataset.npz --output out\nnue_model.pt --epochs 8 --batch-size 512 --hidden-size 64
```

快速測試可先用小樣本：

```powershell
python src\train_nnue.py --input out\policy_dataset.npz --output out\nnue_smoke.pt --epochs 1 --batch-size 128 --max-samples 512 --hidden-size 32
```

目前這是訓練骨架，尚未預設接入 `.bat` 的 AI 決策。建議先觀察 `test_mae`，等 value label 改善後，再把它接成中終盤 evaluator 或 root bonus。


Opening Book

AI 對弈支援從 MySQL 棋譜資料庫建立簡單開局庫。啟動時會統計前 N 手的局面與下一手出現次數；AI 在開局庫命中時會直接走資料庫中最常見的合法手，查不到才進入 alpha-beta 搜尋。

```powershell
python src\csa_browser_api.py --source mysql --db-host 140.135.65.53 --db-port 3306 --db-user 11211213 --db-name DB11211213 --policy-model out\policy_model.pt --value-weight 0 --policy-order-ply 2 --opening-book-ply 30 --opening-book-min-count 2
```

參數意義：

```text
--opening-book-ply 30
只使用前 30 手內的資料建立開局庫。

--opening-book-min-count 2
同一局面下某手至少出現 2 次才會被當成 book move。
```

若資料庫暫時連不上，opening book 會自動停用，AI 會退回原本搜尋流程。


AI Model Match

若要比較舊模型與新模型棋力，可讓兩個模型在相同搜尋設定下自動對弈。預設使用：

```text
old: out\policy_model.prev.pt
new: out\policy_model.pt
```

執行：

```powershell
python src\compare_ai_models.py --games 10 --depth 3 --time-limit-ms 1000 --output-jsonl out\model_match.jsonl
```

它會輪流交換先後手：

```text
第 1 局：new 先手，old 後手
第 2 局：old 先手，new 後手
```

輸出會包含：

```text
new_wins
old_wins
draws
new_score_rate
average_plies
每局完整 USI 走法
```

若要指定模型：

```powershell
python src\compare_ai_models.py --old-model out\policy_model.before_adamw_scheduler.pt --new-model out\policy_model.pt --games 20 --depth 3 --time-limit-ms 1000
```

若對局達到最大手數，預設會用傳統評估做保守裁定；一方優勢超過 `1000` 分才判勝，否則和棋。可調整或關閉：

```powershell
python src\compare_ai_models.py --games 20 --adjudicate-score 1500
python src\compare_ai_models.py --games 20 --adjudicate-score 0
```

然後打開：

notebooks\cshogi_jupyter_viewer.ipynb

cshogi 本來就支援在 Notebook 裡直接顯示棋盤，所以這樣就會看到棋盤：

import cshogi

board = cshogi.Board()
board

如果要看 CSA 的某一步：

from src.notebook_viewer import csa_boards, show

csa = csa_boards("data/game1.csa", encoding="utf-8")
show(csa[0])

如果要看轉好的 .npz 樣本：

from src.notebook_viewer import npz_samples, show, show_many

samples = npz_samples("out/game1.npz")
show(samples[0])
show_many(samples, limit=5)

show() 會把棋盤畫出來，也會順便顯示第幾手、下一手、move label、value、來源檔案和 SFEN。


目前最常用的兩行

轉資料：

python src\csa_preprocess.py --input data\game1.csa --output out\game1.npz --encoding utf-8 --keep-invalid-report out\game1_invalid.jsonl

開 Notebook 看棋盤：

jupyter notebook
