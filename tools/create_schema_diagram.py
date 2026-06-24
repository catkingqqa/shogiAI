from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import html
import math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "db_schema"
OUT.mkdir(parents=True, exist_ok=True)
PNG = OUT / "DB11211213_er_diagram.png"
SVG = OUT / "DB11211213_er_diagram.svg"

W, H = 1900, 1180
BG = "#F6F8FA"
INK = "#1E2A3A"
MUTED = "#5E6B7A"
LINE = "#B8C6D8"
BLUE = "#1D4ED8"
TEAL = "#0F766E"
GREEN = "#059669"
ORANGE = "#D97706"
CARD = "#FFFFFF"
PK = "#EEF6FF"
FK = "#F0FDF4"

FONT_CJK = r"C:\Windows\Fonts\msjh.ttc"
FONT_MONO = r"C:\Windows\Fonts\consola.ttf"


def font(size, mono=False):
    return ImageFont.truetype(FONT_MONO if mono else FONT_CJK, size=size)


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

F_LABEL = font(20)
F_TITLE = font(44)
F_SUB = font(24)
F_TABLE = font(29)
F_FIELD = font(20, mono=True)
F_FIELD_SM = font(18, mono=True)
F_NOTE = font(22)
F_SMALL = font(17)


def text(x, y, s, fnt, fill=INK):
    d.text((x, y), s, font=fnt, fill=fill)


def rounded(box, radius=14, fill=CARD, outline=LINE, width=2):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


text(90, 72, "RELATIONAL MODEL", F_LABEL, TEAL)
text(90, 112, "DB11211213 資料庫結構圖", F_TITLE, INK)
text(90, 176, "由 mysqldump --no-data 匯出的 schema 產生，呈現資料表、主鍵、外鍵與主要關聯。", F_SUB, MUTED)
d.rounded_rectangle((1610, 78, 1710, 94), 8, fill=TEAL)
d.rounded_rectangle((1725, 78, 1825, 94), 8, fill=ORANGE)

boxes = {
    "users": (120, 330, 470, 575),
    "players": (120, 665, 470, 900),
    "game_records": (690, 360, 1190, 790),
    "moves": (1390, 300, 1785, 590),
    "positions": (1390, 690, 1785, 1005),
}

accent = {
    "users": BLUE,
    "players": BLUE,
    "game_records": TEAL,
    "moves": GREEN,
    "positions": ORANGE,
}

tables = {
    "users": [
        ("PK", "user_id int"),
        ("", "username varchar(100)"),
        ("UQ", "email varchar(255)"),
        ("", "password_hash varchar(255)"),
        ("", "role varchar(50)"),
        ("", "created_at datetime"),
    ],
    "players": [
        ("PK", "player_id int"),
        ("", "player_name varchar(100)"),
        ("", "rank_name varchar(50)"),
        ("", "created_at datetime"),
    ],
    "game_records": [
        ("PK", "game_id int"),
        ("FK", "uploader_id -> users"),
        ("FK", "black_player_id -> players"),
        ("FK", "white_player_id -> players"),
        ("", "event_name / site / opening"),
        ("", "result / source_format"),
        ("", "original_file_name"),
        ("", "played_at date"),
        ("", "created_at datetime"),
    ],
    "moves": [
        ("PK", "move_id int"),
        ("FK", "game_id -> game_records"),
        ("", "move_number int"),
        ("", "side_to_move enum"),
        ("", "original_move / usi_move"),
        ("", "move_time / comment"),
        ("", "created_at datetime"),
    ],
    "positions": [
        ("PK", "position_id int"),
        ("FK", "game_id -> game_records"),
        ("", "move_number int"),
        ("", "side_to_move enum"),
        ("", "sfen text"),
        ("", "sfen_hash char(64)"),
        ("", "is_check"),
        ("", "legal_moves_count"),
        ("", "created_at datetime"),
    ],
}


def arrow(p1, p2, color, label):
    x1, y1 = p1
    x2, y2 = p2
    d.line((x1, y1, x2, y2), fill=color, width=4)
    ang = math.atan2(y2 - y1, x2 - x1)
    ah = 18
    pts = [
        (x2, y2),
        (x2 - ah * math.cos(ang - 0.45), y2 - ah * math.sin(ang - 0.45)),
        (x2 - ah * math.cos(ang + 0.45), y2 - ah * math.sin(ang + 0.45)),
    ]
    d.polygon(pts, fill=color)
    tw = d.textlength(label, font=F_SMALL)
    lx = (x1 + x2) // 2 - tw / 2
    ly = (y1 + y2) // 2 - 18
    rounded((lx - 10, ly - 4, lx + tw + 10, ly + 28), 8, BG, color, 2)
    text(lx, ly, label, F_SMALL, INK)


arrow((470, 455), (690, 470), "#7CA3D8", "1:N uploader")
arrow((470, 785), (690, 590), "#7CA3D8", "1:N black / white")
arrow((1190, 475), (1390, 445), "#7FC8A9", "1:N game_id")
arrow((1190, 675), (1390, 835), "#E2A44E", "1:N game_id")
d.line((1390, 630, 1785, 630), fill="#94A3B8", width=3)
text(1425, 604, "move_number 對齊：Position_t 對應 Move_{t+1}", F_SMALL, MUTED)


def draw_table(name):
    x1, y1, x2, y2 = boxes[name]
    rounded((x1 + 8, y1 + 8, x2 + 8, y2 + 8), 14, "#E4EAF2", "#E4EAF2", 0)
    rounded((x1, y1, x2, y2), 14, CARD, LINE, 2)
    d.rounded_rectangle((x1, y1, x2, y1 + 58), 14, fill=accent[name])
    d.rectangle((x1, y1 + 38, x2, y1 + 58), fill=accent[name])
    text(x1 + 22, y1 + 13, name, F_TABLE, "white")
    y = y1 + 80
    for tag, field in tables[name]:
        if tag:
            fill = PK if tag == "PK" else FK if tag == "FK" else "#FFF7ED"
            color = BLUE if tag == "PK" else GREEN if tag == "FK" else ORANGE
            rounded((x1 + 20, y - 3, x1 + 66, y + 25), 7, fill, color, 1)
            text(x1 + 29, y, tag, F_SMALL, color)
            tx = x1 + 82
        else:
            tx = x1 + 24
        text(tx, y, field, F_FIELD_SM if len(field) > 27 else F_FIELD, INK)
        y += 34


for table in boxes:
    draw_table(table)

rounded((90, 1040, 1810, 1108), 12, "#EAF3F7", "#B9D6E2", 2)
text(
    120,
    1060,
    "設計重點：game_records 是棋局主表；moves 與 positions 透過 game_id 關聯到棋局，並用 move_number 支援回放與訓練資料對齊。",
    F_NOTE,
    INK,
)
text(90, 1135, "shogiAI 資料庫系統｜Schema ER Diagram｜DB11211213_schema_20260624.sql", F_SMALL, MUTED)

img.save(PNG, quality=95)

svg = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
    f'<rect width="{W}" height="{H}" fill="{BG}"/>',
    '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#94A3B8"/></marker></defs>',
]


def svg_text(x, y, s, size=22, fill=INK, weight="400", family="Microsoft JhengHei, Noto Sans TC"):
    svg.append(
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{fill}">{html.escape(s)}</text>'
    )


def svg_rect(x, y, w, h, fill=CARD, stroke=LINE, rx=12, sw=2):
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def svg_line(x1, y1, x2, y2, stroke, label):
    svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="4" marker-end="url(#arrow)"/>')
    svg_text((x1 + x2) // 2 - 52, (y1 + y2) // 2 - 8, label, 17, MUTED)


svg_text(90, 95, "RELATIONAL MODEL", 20, TEAL, "700")
svg_text(90, 150, "DB11211213 資料庫結構圖", 44, INK, "700")
svg_text(90, 200, "由 mysqldump --no-data 匯出的 schema 產生，呈現資料表、主鍵、外鍵與主要關聯。", 24, MUTED)
for p1, p2, label, color in [
    ((470, 455), (690, 470), "1:N uploader", "#7CA3D8"),
    ((470, 785), (690, 590), "1:N black / white", "#7CA3D8"),
    ((1190, 475), (1390, 445), "1:N game_id", "#7FC8A9"),
    ((1190, 675), (1390, 835), "1:N game_id", "#E2A44E"),
]:
    svg_line(*p1, *p2, color, label)

for name, (x1, y1, x2, y2) in boxes.items():
    svg_rect(x1, y1, x2 - x1, y2 - y1)
    svg.append(f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="58" rx="12" fill="{accent[name]}"/>')
    svg_text(x1 + 22, y1 + 39, name, 29, "white", "700")
    y = y1 + 97
    for tag, field in tables[name]:
        svg_text(x1 + 24, y, (tag + "  " if tag else "    ") + field, 20, INK, "400", "Consolas, Microsoft JhengHei")
        y += 34

svg_rect(90, 1040, 1720, 68, "#EAF3F7", "#B9D6E2")
svg_text(120, 1080, "設計重點：game_records 是棋局主表；moves 與 positions 透過 game_id 關聯到棋局，並用 move_number 支援回放與訓練資料對齊。", 22, INK)
svg_text(90, 1150, "shogiAI 資料庫系統｜Schema ER Diagram｜DB11211213_schema_20260624.sql", 17, MUTED)
svg.append("</svg>")
SVG.write_text("\n".join(svg), encoding="utf-8")

print(PNG)
print(SVG)
