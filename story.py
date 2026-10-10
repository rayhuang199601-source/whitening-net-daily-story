"""白凝每日可預約限動：讀取、排版與合成品牌配樂。

執行：python story.py --sample（本機預覽）；正式發布入口見 workflow.py。
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import json
import os
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

TZ = ZoneInfo("Asia/Taipei")
AVAIL_TITLE = "牙齒淨白_可預約"
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
W, H = 1080, 1920
WEEKDAYS = "一二三四五六日"


def choose_slots(events: list[dict], now: dt.datetime, days=3, lookahead=21) -> list[dict]:
    """沿用既有 DailySlotPush.gs：找出接下來 3 個有空檔的日期。

    可預約事件必須完整覆蓋一小時；同一本行事曆其他事件與該小時重疊即排除。
    """
    result = []
    for offset in range(lookahead):
        day = now.date() + dt.timedelta(days=offset)
        free, busy = [], []
        for event in events:
            if "dateTime" not in event.get("start", {}):
                continue
            start = dt.datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00")).astimezone(TZ)
            end = dt.datetime.fromisoformat(event["end"]["dateTime"].replace("Z", "+00:00")).astimezone(TZ)
            if start.date() > day or end.date() < day:
                continue
            (free if event.get("summary") == AVAIL_TITLE else busy).append((start, end))
        hours = []
        for hour in range(8, 23):
            start = dt.datetime.combine(day, dt.time(hour), TZ)
            end = start + dt.timedelta(hours=1)
            if start < now or not any(a <= start and end <= b for a, b in free):
                continue
            if any(a < end and b > start for a, b in busy):
                continue
            hours.append(f"{hour:02d}:00")
        if hours:
            result.append({"date": day.isoformat(), "hours": hours})
        if len(result) == days:
            break
    return result


def fetch_events(now: dt.datetime) -> list[dict]:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    calendar_id = os.getenv("CALENDAR_ID")
    if not calendar_id:
        raise RuntimeError("缺少 CALENDAR_ID 環境變數")
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/calendar.readonly"])
    session = AuthorizedSession(credentials)
    params = {
        "timeMin": dt.datetime.combine(now.date(), dt.time.min, TZ).isoformat(),
        "timeMax": dt.datetime.combine(now.date() + dt.timedelta(days=21), dt.time.min, TZ).isoformat(),
        "singleEvents": "true", "maxResults": "2500", "timeZone": "Asia/Taipei",
    }
    url = "https://www.googleapis.com/calendar/v3/calendars/" + __import__("urllib.parse").parse.quote(calendar_id, safe="") + "/events"
    events = []
    while True:
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        events += data.get("items", [])
        if not data.get("nextPageToken"):
            break
        params["pageToken"] = data["nextPageToken"]
    return events


def text_font(size: int) -> ImageFont.FreeTypeFont:
    local = Path(__file__).parents[2] / "carousel/2026-W42/v2/fonts/NotoSansTC-Medium.ttf"
    candidates = [local, Path(FONT), Path("/System/Library/Fonts/PingFang.ttc")]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise FileNotFoundError("缺少繁體中文字型，請提供 NotoSansTC-Regular.otf")


def serif_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [(Path("/usr/share/fonts/opentype/noto/" +
                        ("NotoSerifCJK-Bold.ttc" if bold else "NotoSerifCJK-Regular.ttc")), 3),
                  (Path("/System/Library/Fonts/Supplemental/Songti.ttc"), 2 if bold else 7)]
    for path, index in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size, index=index)
    return text_font(size)


def render(slots: list[dict], path: Path) -> None:
    photo_path = Path(__file__).parent / "brand_photo.jpg"
    if photo_path.exists():
        with Image.open(photo_path) as source:
            image = ImageOps.fit(source.convert("RGB"), (W, H), method=Image.Resampling.LANCZOS)
    else:
        image = Image.new("RGB", (W, H), "#f6f4f0")
    image = image.convert("RGBA")
    ink, blue = "#324455", "#819eb5"
    draw = ImageDraw.Draw(image)

    # 影像只提供氛圍；日期、時段和品牌字均由程式精確排版。
    draw.text((78, 117), "Good Morning!", font=serif_font(45), fill=blue)
    draw.text((68, 235), "近期可", font=serif_font(105, bold=True), fill=ink)
    draw.text((68, 350), "預約時段", font=serif_font(105, bold=True), fill=ink)
    draw.arc((96, 493, 540, 585), 190, 350, fill=blue, width=4)
    draw.text((79, 548), "留一點時間給自己，", font=serif_font(37), fill=ink)
    draw.text((79, 605), "從容整理笑容", font=serif_font(37), fill=ink)

    card_top, row_height = 770, 213
    card_bottom = card_top + 55 + row_height * len(slots)
    shadow = Image.new("RGBA", (W, H))
    ImageDraw.Draw(shadow).rounded_rectangle((55, card_top + 15, 1030, card_bottom + 15),
        radius=48, fill=(48, 61, 75, 65))
    image = Image.alpha_composite(image, shadow.filter(ImageFilter.GaussianBlur(25)))
    panel = Image.new("RGBA", (W, H))
    panel_draw = ImageDraw.Draw(panel)
    panel_draw.rounded_rectangle((45, card_top, 1035, card_bottom), radius=48,
        fill=(255, 254, 251, 246), outline=(224, 229, 231, 255), width=2)
    image = Image.alpha_composite(image, panel)
    draw = ImageDraw.Draw(image)

    for i, row in enumerate(slots):
        date = dt.date.fromisoformat(row["date"])
        center_y = card_top + 148 + i * row_height
        draw.ellipse((105, center_y - 87, 279, center_y + 87), fill="#e6edf2")
        draw.text((192, center_y - 30), f"{date.month}/{date.day}",
                  font=serif_font(58), fill=ink, anchor="mm")
        draw.text((192, center_y + 43), f"（{WEEKDAYS[date.weekday()]}）",
                  font=serif_font(36), fill=ink, anchor="mm")
        draw.line((330, center_y - 74, 330, center_y + 74), fill="#a8bccb", width=2)
        hours = row["hours"]
        columns = 5 if len(hours) > 12 else 4
        line_count = math.ceil(len(hours) / columns)
        first_y = center_y - (line_count - 1) * 26
        for j, hour in enumerate(hours):
            x = 386 + (j % columns) * (121 if columns == 5 else 149)
            y = first_y + (j // columns) * 52
            draw.text((x, y), hour, font=serif_font(35), fill=ink, anchor="lm")
        if i < len(slots) - 1:
            y = center_y + 108
            draw.line((83, y, 995, y), fill="#e0e4e7", width=2)

    draw.rounded_rectangle((220, 1550, 860, 1660), radius=55, fill="#8caabd")
    draw.text((540, 1604), "歡迎私訊預約  ›", font=serif_font(52), fill="#ffffff", anchor="mm")
    draw.text((540, 1704), "實際時段以私訊確認為準", font=serif_font(29), fill=ink, anchor="mm")
    draw.line((270, 1754, 810, 1754), fill="#a2b5c4", width=2)
    draw.text((540, 1812), "WHITENING NET", font=serif_font(47), fill=ink, anchor="mm")
    draw.text((540, 1861), "白凝｜美齒計畫  台北師大店", font=serif_font(30), fill=ink, anchor="mm")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, quality=94)


def video(image: Path, output: Path) -> None:
    music = Path(__file__).parent / "brand_music.mp3"
    if not music.is_file():
        raise FileNotFoundError(f"缺少品牌配樂：{music}")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "25",
                    "-i", str(image), "-i", str(music), "-t", "8", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-r", "25", "-c:a", "aac", "-ar", "48000", "-b:a", "128k", "-movflags", "+faststart", str(output)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("out"))
    args = parser.parse_args()
    if args.sample:
        slots = [{"date": "2026-10-07", "hours": [f"{h:02d}:00" for h in range(14,21)]},
                 {"date": "2026-10-08", "hours": ["13:00", "14:00", "15:00", "17:00", "20:00"]},
                 {"date": "2026-10-09", "hours": [f"{h:02d}:00" for h in range(12,21)]}]
    else:
        now = dt.datetime.now(TZ)
        slots = choose_slots(fetch_events(now), now)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "slots.json").write_text(json.dumps(slots, ensure_ascii=False, indent=2), encoding="utf-8")
    if slots:
        render(slots, args.output / "story.jpg")
        video(args.output / "story.jpg", args.output / "story.mp4")
    print(json.dumps({"slots": slots, "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
