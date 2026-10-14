"""白凝桌面攝影風限動版型；日期與時段由行事曆資料精確繪製。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).parent
BACKGROUND = ROOT / "assets" / "tabletop_background.jpg"
SIZE = (1080, 1920)
INK = "#302d28"
MUTED = "#625e55"
RULE = "#89877f"
WEEKDAYS = "一二三四五六日"


def font(size: int, *, latin: bool = False) -> ImageFont.FreeTypeFont:
    if latin:
        candidates = [
            ("/System/Library/Fonts/Supplemental/Times New Roman.ttf", 0),
            ("/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf", 0),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 0),
        ]
    else:
        candidates = [
            ("/System/Library/Fonts/Supplemental/Songti.ttc", 2),
            ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 3),
        ]
    for path, index in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size, index=index)
    raise FileNotFoundError("缺少限動字型：請安裝 Noto Serif CJK 與 Liberation Serif")


def spaced(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, *, size: int, gap: int) -> None:
    face = font(size, latin=True)
    for char in value:
        draw.text((x, y), char, font=face, fill=MUTED)
        x += draw.textlength(char, font=face) + gap


def time_line(draw: ImageDraw.ImageDraw, times: list[str], y: int, *, size: int) -> None:
    columns = 5 if len(times) == 5 else 4
    starts = [105, 286, 467, 648, 829] if columns == 5 else [105, 338, 571, 804]
    face = font(size, latin=True)
    for index, value in enumerate(times):
        draw.text((starts[index], y), value, font=face, fill=INK)
        if index < len(times) - 1:
            line_x = starts[index + 1] - 27
            draw.line((line_x, y + 6, line_x, y + size + 3), fill=RULE, width=2)


def render_tabletop(slots: list[dict], output: Path) -> None:
    if not 1 <= len(slots) <= 3:
        raise ValueError("桌面版限動需要一至三個可預約日")
    if any(len(row["hours"]) > 15 for row in slots):
        raise ValueError("單日可預約時段超過桌面版容量")
    with Image.open(BACKGROUND) as source:
        image = ImageOps.fit(source.convert("RGB"), SIZE, method=Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)

    spaced(draw, 103, 146, "WHITENING NET", size=25, gap=7)
    draw.text((97, 296), "近期可預約時段", font=font(82), fill=INK)
    draw.line((104, 405, 423, 405), fill=RULE, width=2)
    spaced(draw, 105, 424, "RESERVATION", size=27, gap=9)
    draw.text((103, 495), "留一點時間，給自己的笑容。", font=font(32), fill=MUTED)

    compact = any(len(row["hours"]) > 10 for row in slots)
    row_tops = [600, 830, 1060] if compact else [627, 852, 1137]
    row_bottoms = [820, 1050, 1280] if compact else [817, 1097, 1317]
    for row, top, bottom in zip(slots, row_tops, row_bottoms):
        day = date.fromisoformat(row["date"])
        draw.text((102, top), f"{day.month:02d}/{day.day:02d}", font=font(64, latin=True), fill=INK)
        draw.text((306, top + 14), f"（{WEEKDAYS[day.weekday()]}）", font=font(32), fill=MUTED)
        lines = [row["hours"][i:i + 5] for i in range(0, len(row["hours"]), 5)]
        if len(lines) == 1:
            positions, size = [top + 94], 40
        elif len(lines) == 2 and bottom - top >= 240:
            positions, size = [top + 88, top + 154], 40
        elif len(lines) == 2:
            positions, size = [top + 80, top + 133], 37
        else:
            positions, size = [top + 75, top + 122, top + 169], 34
        for values, y in zip(lines, positions):
            time_line(draw, values, y, size=size)
        draw.line((103, bottom, 977, bottom), fill=RULE, width=2)

    draw.text((103, 1574), "私訊立即預約  →", font=font(49), fill=INK)
    draw.line((103, 1650, 489, 1650), fill=INK, width=2)
    draw.text((103, 1740), "白凝｜美齒計畫  台北師大店", font=font(27), fill=INK)
    draw.text((103, 1783), "實際時段以私訊確認為準", font=font(23), fill=MUTED)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=94)
