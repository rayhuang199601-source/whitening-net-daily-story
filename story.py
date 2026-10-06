"""白凝每日可預約限動：讀取、排版與合成原創純音樂。

執行：python story.py --sample（本機預覽）；正式發布入口見 workflow.py。
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import json
import os
import struct
import subprocess
import wave
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

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


def render(slots: list[dict], path: Path) -> None:
    image = Image.new("RGB", (W, H), "#f6f4f0")
    draw = ImageDraw.Draw(image)
    photo_path = Path(__file__).parent / "brand_photo.jpg"
    if photo_path.exists():
        source = Image.open(photo_path).convert("RGB")
        scale = max(W / source.width, 870 / source.height)
        source = source.resize((round(source.width * scale), round(source.height * scale)))
        x = (source.width - W) // 2
        source = source.crop((x, 0, x + W, 870))
        image.paste(source, (0, 0))
        overlay = Image.new("RGBA", (W, 870), (248, 247, 244, 85))
        image.paste(overlay, (0, 0), overlay)
        draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((52, 70, 690, 200), radius=42, fill="#e4ebf0")
    draw.text((88, 100), "WHITE NING NET", font=text_font(40), fill="#5c7994")
    draw.text((70, 238), "近期可預約時段", font=text_font(83), fill="#303743")
    draw.text((72, 355), "留一點時間給自己，從微笑開始", font=text_font(39), fill="#52606c")
    draw.rounded_rectangle((48, 510, 1032, 1620), radius=48, fill="#fffdf9", outline="#d4dfe8", width=3)
    top = 560
    for i, row in enumerate(slots):
        date = dt.date.fromisoformat(row["date"])
        label = f"{date.month}/{date.day}（{WEEKDAYS[date.weekday()]}）"
        draw.text((95, top), label, font=text_font(58), fill="#364556")
        hours = row["hours"]
        for j in range(0, len(hours), 4):
            draw.text((100, top + 94 + (j // 4) * 57), "  ·  ".join(hours[j:j+4]), font=text_font(40), fill="#3c4e60")
        if i < len(slots)-1:
            draw.line((90, top + 310, 990, top + 310), fill="#dbe3e9", width=3)
        top += 350
    draw.rounded_rectangle((155, 1690, 925, 1800), radius=54, fill="#8ca9bd")
    draw.text((360, 1714), "歡迎私訊預約", font=text_font(47), fill="#ffffff")
    draw.text((252, 1840), "白凝｜美齒計畫  台北師大店", font=text_font(34), fill="#617a8c")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, quality=94)


def synth_music(path: Path, seconds=8) -> None:
    """自行合成柔和明亮的四小節純音樂，不使用受版權保護的錄音。"""
    rate = 24000
    chords = [(261.63, 329.63, 392.00), (220.00, 329.63, 440.00),
              (174.61, 261.63, 349.23), (196.00, 293.66, 392.00)]
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1); file.setsampwidth(2); file.setframerate(rate)
        frames = bytearray()
        for n in range(rate * seconds):
            t = n / rate
            chord = chords[min(int(t // 2), 3)]
            local = t % 2
            envelope = min(local / .25, 1, (2 - local) / .28)
            tone = sum(math.sin(2 * math.pi * f * t) for f in chord) / 3
            sparkle = math.sin(2 * math.pi * chord[2] * 2 * t) * .09
            sample = max(-1, min(1, (tone * .25 + sparkle) * envelope))
            frames += struct.pack("<h", round(sample * 32767))
        file.writeframes(frames)


def video(image: Path, output: Path) -> None:
    music = output.with_suffix(".wav")
    synth_music(music)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "25",
                    "-i", str(image), "-i", str(music), "-t", "8", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-r", "25", "-c:a", "aac", "-ar", "48000", "-b:a", "128k", "-movflags", "+faststart", str(output)], check=True)
    music.unlink()


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
