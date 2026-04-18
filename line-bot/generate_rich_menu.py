"""生成 LINE Rich Menu 圖片並自動上傳（6 格 3×2，2500×1686 px）白底風格"""
import json
import os
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 2500, 1686
COLS, ROWS = 3, 2
CW, CH = W // COLS, H // ROWS  # 833 × 843

ICON_DIR = Path("C:/Users/kancer/Desktop/新增資料夾 (7)/新增資料夾")

BG        = (255, 255, 255)
CELL_BG   = (252, 252, 255)
LABEL_C   = (20,  30,  90)
SUB_C     = (60,  80, 180)
DIV_V     = (210, 215, 230)   # 垂直格線

# 橫排分隔色（上色帶 / 列間色帶）
STRIPE_TOP = [(80,200,80),(120,220,60),(255,200,0),(255,140,0),(220,50,50),(180,0,200),(0,120,220)]
SEP_ROW1   = (60, 80, 200)   # 第一列底部
SEP_ROW1_W = 8

FONT    = "C:/Windows/Fonts/NotoSansTC-VF.ttf"
f_label = ImageFont.truetype(FONT, 108)
f_label.set_variation_by_name("Black")
f_sub = ImageFont.truetype(FONT, 76)
f_sub.set_variation_by_name("Bold")

CELLS = [
    ("sun",      "早安・今日好料", "每日晨間補給"),
    ("ramen",    "今天吃什麼",   "探索周邊美食"),
    ("calendar", "近期活動",    "選地區・活動推薦"),
    ("parking",  "找車位",      "傳位置→即時空位"),
    ("piggy",    "生活工具",    "健康・金錢・3C"),
    ("wrench",   "更多功能",    "所有功能一覽"),
]


def find_icon(keyword: str) -> Path | None:
    for f in ICON_DIR.iterdir():
        if keyword in f.name.lower():
            return f
    return None


def draw_rainbow_stripe(draw: ImageDraw.ImageDraw, y: int, stripe_h: int = 18) -> None:
    seg = W // len(STRIPE_TOP)
    for i, c in enumerate(STRIPE_TOP):
        x0 = i * seg
        x1 = x0 + seg if i < len(STRIPE_TOP) - 1 else W
        draw.rectangle([x0, y, x1, y + stripe_h - 1], fill=c)


def paste_icon(canvas: Image.Image, path: Path, col: int, row: int) -> None:
    x0, y0 = col * CW, row * CH
    icon_area_h = int(CH * 0.58)   # icon 佔格高上半 58%
    max_size = int(min(CW, icon_area_h) * 0.90)

    raw = Image.open(path).convert("RGB")
    raw.thumbnail((max_size, max_size), Image.LANCZOS)

    iw, ih = raw.size
    ix = x0 + (CW - iw) // 2
    iy = y0 + (icon_area_h - ih) // 2 + 20   # 略往下偏留頂部空間
    canvas.paste(raw, (ix, iy))


def draw_text(draw: ImageDraw.ImageDraw, col: int, row: int, label: str, sub: str) -> None:
    cx = col * CW + CW // 2
    y0 = row * CH
    max_w = CW - 40

    ly = y0 + int(CH * 0.68)
    draw.text((cx, ly), label, font=f_label, fill=LABEL_C, anchor="mm")

    sy = y0 + int(CH * 0.84)
    draw.text((cx, sy), sub, font=f_sub, fill=SUB_C, anchor="mm")


def main() -> None:
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)

    # 儲存格背景
    for row in range(ROWS):
        for col in range(COLS):
            x0, y0 = col * CW, row * CH
            draw.rectangle([x0, y0, x0 + CW - 1, y0 + CH - 1], fill=CELL_BG)

    # 貼圖 & 文字
    for i, (kw, label, sub) in enumerate(CELLS):
        col, row = i % COLS, i // COLS
        path = find_icon(kw)
        if path:
            paste_icon(canvas, path, col, row)
        else:
            print(f"[WARN] icon not found: {kw}")
        draw_text(draw, col, row, label, sub)

    # 頂部彩虹色帶
    draw_rainbow_stripe(draw, 0, 22)

    # 列間色帶
    ry = CH
    draw.rectangle([0, ry - SEP_ROW1_W // 2, W, ry + SEP_ROW1_W // 2], fill=SEP_ROW1)

    # 垂直格線
    for c in range(1, COLS):
        x = c * CW
        draw.line([(x, 0), (x, H)], fill=DIV_V, width=3)

    out = "rich_menu_6grid.png"
    canvas.save(out, quality=95)
    print(f"saved → {out}  ({W}×{H})")
    return Path(out)


def upload(img_path: Path) -> None:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        print("ERROR: please set LINE_CHANNEL_ACCESS_TOKEN")
        return

    h = {"Authorization": f"Bearer {token}"}

    # 1. 建新 Rich Menu
    menu_cfg = {
        "size": {"width": 2500, "height": 1686},
        "selected": True,
        "name": "生活優轉選單 v3",
        "chatBarText": "✨ 點我開啟功能選單",
        "areas": [
            {"bounds": {"x": 0,    "y": 0,   "width": 833,  "height": 843},
             "action": {"type": "message", "label": "早安・今日好料", "text": "早安"}},
            {"bounds": {"x": 833,  "y": 0,   "width": 834,  "height": 843},
             "action": {"type": "message", "label": "今天吃什麼", "text": "今天吃什麼"}},
            {"bounds": {"x": 1667, "y": 0,   "width": 833,  "height": 843},
             "action": {"type": "message", "label": "近期活動", "text": "近期活動"}},
            {"bounds": {"x": 0,    "y": 843, "width": 833,  "height": 843},
             "action": {"type": "message", "label": "找車位", "text": "找車位"}},
            {"bounds": {"x": 833,  "y": 843, "width": 834,  "height": 843},
             "action": {"type": "message", "label": "生活工具", "text": "生活工具"}},
            {"bounds": {"x": 1667, "y": 843, "width": 833,  "height": 843},
             "action": {"type": "message", "label": "更多功能", "text": "更多功能"}},
        ],
    }
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/richmenu",
        data=json.dumps(menu_cfg, ensure_ascii=False).encode(),
        headers={**h, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        new_id = json.loads(r.read())["richMenuId"]
    print(f"created richMenuId={new_id}")

    # 2. 上傳圖片
    img_data = img_path.read_bytes()
    up_req = urllib.request.Request(
        f"https://api-data.line.me/v2/bot/richmenu/{new_id}/content",
        data=img_data,
        headers={**h, "Content-Type": "image/png"},
    )
    urllib.request.urlopen(up_req, timeout=30).close()
    print("image uploaded")

    # 3. 設為全體預設
    urllib.request.urlopen(
        urllib.request.Request(
            f"https://api.line.me/v2/bot/user/all/richmenu/{new_id}",
            data=b"", method="POST", headers=h,
        ), timeout=10
    ).close()
    print("set as default OK")

    # 4. 刪舊的
    with urllib.request.urlopen(
        urllib.request.Request("https://api.line.me/v2/bot/richmenu/list", headers=h),
        timeout=10,
    ) as r:
        old_menus = json.loads(r.read())["richmenus"]

    for m in old_menus:
        mid = m["richMenuId"]
        if mid == new_id:
            continue
        try:
            urllib.request.urlopen(
                urllib.request.Request(
                    f"https://api.line.me/v2/bot/richmenu/{mid}",
                    method="DELETE", headers=h,
                ), timeout=10
            ).close()
            print(f"deleted old {mid}")
        except Exception as e:
            print(f"delete failed {mid}: {e}")


if __name__ == "__main__":
    img = main()
    upload(img)
