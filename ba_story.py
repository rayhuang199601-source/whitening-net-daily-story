"""每日交錯輪播兩批加密齒色對比限動；首發為 2026-10-25 中午。"""
from __future__ import annotations

import datetime as dt
import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests
from cryptography.fernet import Fernet, InvalidToken
from PIL import Image

from story import TZ, video
from workflow import (gh_file, gh_write, notify, public_video_url, publish_story,
                      refresh_meta_token, required)

START_DAY = dt.date(2026, 10, 25)
STORY_COUNT = 16
ASSET_DIR = Path(__file__).parent / "assets" / "ba_story"


def index_for(day: dt.date) -> int:
    if day < START_DAY:
        raise ValueError("BA 輪播尚未開始")
    position = (day - START_DAY).days % STORY_COUNT
    # 10/25 舊第 1 張、10/26 新第 1 張，之後逐日交錯。
    return position // 2 + (1 if position % 2 == 0 else 9)


def state_path(day: dt.date) -> str:
    return f"state/ba-story-{day.isoformat()}.json"


def claim_day(path: str, data: dict, today: dt.date) -> bool:
    """只建立新狀態檔；既有檔案不能被另一個排程覆寫。"""
    repo = required("GITHUB_REPOSITORY")
    branch = os.getenv("GH_STATE_BRANCH", "main")
    response = requests.put(
        f"https://api.github.com/repos/{repo}/contents/{path}",
        headers={"Authorization": f"Bearer {required('GITHUB_TOKEN')}",
                 "Accept": "application/vnd.github+json"},
        json={"message": f"Mark BA Story pending {today}",
              "content": base64.b64encode(json.dumps(data, ensure_ascii=False).encode()).decode(),
              "branch": branch}, timeout=60)
    if response.status_code in (409, 422) and gh_file(path):
        return False
    response.raise_for_status()
    return True


def output_flag(publish: bool) -> None:
    path = Path(os.getenv("GITHUB_OUTPUT", "out/step-output.txt"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"publish={'true' if publish else 'false'}\n")


def wait_until_noon() -> None:
    if os.getenv("GITHUB_EVENT_NAME") not in ("schedule", "workflow_dispatch"):
        return
    if os.getenv("GITHUB_EVENT_NAME") != "schedule" and os.getenv("SCHEDULED_DISPATCH") != "true":
        return
    now = dt.datetime.now(TZ)
    target = dt.datetime.combine(now.date(), dt.time(12), TZ)
    delay = (target - now).total_seconds()
    if 0 < delay <= 900:
        time.sleep(delay)


def decrypt_image(index: int, output: Path) -> None:
    encrypted = (ASSET_DIR / f"{index:02d}.png.enc").read_bytes()
    try:
        image = Fernet(required("BA_IMAGE_KEY").encode()).decrypt(encrypted)
    except (ValueError, InvalidToken) as error:
        raise RuntimeError("BA 圖片解密失敗；請檢查 GitHub Secret") from error
    output.write_bytes(image)
    with Image.open(output) as loaded:
        if loaded.size != (1080, 1920) or loaded.format != "PNG":
            raise RuntimeError("BA 限動圖片格式或尺寸不正確")


def prepare() -> None:
    wait_until_noon()
    today = dt.datetime.now(TZ).date()
    dry_run = os.getenv("DRY_RUN") == "true"
    rendering_day = max(today, START_DAY) if dry_run else today
    output_flag(False)
    if today < START_DAY and not dry_run:
        print("BA 限動首發日期尚未到，略過")
        return
    if not dry_run and gh_file(state_path(today)):
        print("今日 BA 限動已有發布或待查紀錄，避免重複發布")
        return
    if not dry_run:
        refresh_meta_token()
    output = Path("out")
    output.mkdir(exist_ok=True)
    index = index_for(rendering_day)
    decrypt_image(index, output / "ba_story.png")
    music = video(output / "ba_story.png", output / "ba_story.mp4", rendering_day)
    content = (output / "ba_story.mp4").read_bytes()
    asset_path = f"story/ba-{rendering_day.isoformat()}_{hashlib.sha256(content).hexdigest()[:12]}.mp4"
    public_file = Path("site") / asset_path
    public_file.parent.mkdir(parents=True, exist_ok=True)
    public_file.write_bytes(content)
    (output / "ba_manifest.json").write_text(json.dumps({
        "day": rendering_day.isoformat(), "index": index, "path": asset_path,
        "size": len(content), "music": music.name,
    }, ensure_ascii=False))
    output_flag(True)
    print(f"BA 限動已準備：第 {index} 張，日期 {rendering_day.isoformat()}")


def publish() -> None:
    manifest = json.loads(Path("out/ba_manifest.json").read_text())
    today = dt.datetime.now(TZ).date()
    if manifest["day"] != today.isoformat() or manifest["index"] != index_for(today):
        raise RuntimeError("BA 限動日期或輪播順序已變，停止發布")
    path = state_path(today)
    if gh_file(path):
        print("今日 BA 限動已有紀錄，略過重複發布")
        return
    url = public_video_url(manifest["path"], manifest["size"])
    pending = {"status": "pending", "index": manifest["index"],
               "video": url, "music": manifest["music"]}
    if not claim_day(path, pending, today):
        print("另一個排程已先取得今日發布權，略過")
        return
    media_id = publish_story(url)
    published = {**pending, "status": "published", "media_id": media_id}
    gh_write(path, json.dumps(published, ensure_ascii=False).encode(),
             f"Mark BA Story published {today}")
    notify(f"【白凝 BA 限動】{today} 已發布第 {manifest['index']} 張至 @wntw_shida；媒體 ID：{media_id}。")


def verify() -> None:
    manifest = json.loads(Path("out/ba_manifest.json").read_text())
    public_video_url(manifest["path"], manifest["size"])
    print(f"BA 限動公開影片驗證通過：第 {manifest['index']} 張")


if __name__ == "__main__":
    try:
        {"prepare": prepare, "verify": verify, "publish": publish}[sys.argv[1]]()
    except Exception as error:
        try:
            notify(f"【白凝 BA 限動】自動發布失敗，請檢查 GitHub Actions。原因：{str(error)[:250]}")
        finally:
            raise
