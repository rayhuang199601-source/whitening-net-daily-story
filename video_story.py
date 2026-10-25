"""Select an authorized Instagram Reel and publish it as a directly playing Story."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from story import TZ
from workflow import TOKEN_STATE, gh_file, gh_write, graph, notify, public_video_url, publish_story

ROTATION = "state/video-story-rotation.json"
COLLAB_PAGE_ID = "670178586181279"  # Whitening Net 台北師大店
COLLAB_GRAPH = "https://graph.facebook.com/v26.0"
MAX_SOURCE_BYTES = 100 * 1024 * 1024
MAX_DURATION = 60.0


def json_file(path: str) -> dict | None:
    saved = gh_file(path)
    return json.loads(base64.b64decode(saved["content"])) if saved else None


def update_rotation(rotation: dict, source_id: str, available_ids: list[str], day: str) -> dict:
    used = [id_ for id_ in rotation.get("used_ids", []) if id_ in available_ids]
    if source_id in used:
        used = []
    used.append(source_id)
    return {"used_ids": used, "last_id": source_id, "last_date": day}


def reconcile_rotation(rotation: dict, today: dt.date) -> dict:
    """Repair a published day if its later rotation write failed."""
    last_date = rotation.get("last_date", "")
    for offset in range(7, -1, -1):
        day = (today - dt.timedelta(days=offset)).isoformat()
        if day <= last_date:
            continue
        record = json_file(f"state/video-story-{day}.json")
        if record and record.get("status") == "published":
            rotation = update_rotation(rotation, record["source_id"], record["available_ids"], day)
            gh_write(ROTATION, json.dumps(rotation, ensure_ascii=False).encode(),
                f"Repair video Story rotation {day}")
            last_date = day
    return rotation


def account_id() -> str:
    identity = json_file(TOKEN_STATE)
    if not identity or identity.get("username") != "wntw_shida" or not str(identity.get("user_id", "")).isdigit():
        raise RuntimeError("Instagram 授權帳號紀錄無效")
    return str(identity["user_id"])


def list_videos(user_id: str) -> list[dict]:
    """Only use media URLs returned by Instagram for the authorized account."""
    videos: list[dict] = []
    after = None
    for _ in range(10):
        params = {"fields": "id,media_type,media_url,permalink,timestamp", "limit": 100}
        if after:
            params["after"] = after
        result = graph("GET", f"{user_id}/media", params=params)
        for item in result.get("data", []):
            if item.get("media_type") == "VIDEO" and item.get("media_url") and str(item.get("id", "")).isdigit():
                videos.append(item)
        new_after = result.get("paging", {}).get("cursors", {}).get("after")
        if not result.get("paging", {}).get("next") or not new_after or new_after == after:
            break
        after = new_after
    return videos


def facebook_get(path: str, token: str, params: dict | None = None) -> dict:
    """Keep the Facebook Login token out of URLs and exception messages."""
    response = requests.get(f"{COLLAB_GRAPH}/{path}",
        headers={"Authorization": f"Bearer {token}"}, params=params or {}, timeout=30)
    response.raise_for_status()
    return response.json()


def list_collaborative_reels(token: str) -> list[dict]:
    """Read accepted, creator-owned collaborations through Facebook Login."""
    page = facebook_get(COLLAB_PAGE_ID, token,
        {"fields": "instagram_business_account{id,username}"})
    account = page.get("instagram_business_account") or {}
    if account.get("username") != "wntw_shida" or not str(account.get("id", "")).isdigit():
        raise RuntimeError("協作權杖未連到 @wntw_shida，停止讀取")
    videos: list[dict] = []
    after = None
    for _ in range(10):
        params = {"fields": "id,media_type,media_product_type,media_url,permalink,timestamp,username",
            "limit": 100}
        if after:
            params["after"] = after
        result = facebook_get(f"{account['id']}/collaborative_media", token, params)
        for item in result.get("data", []):
            is_reel = item.get("media_product_type") == "REELS" or "/reel/" in item.get("permalink", "")
            if item.get("media_type") == "VIDEO" and is_reel and item.get("media_url") \
                    and str(item.get("id", "")).isdigit():
                videos.append({**item, "source_kind": "collaboration"})
        new_after = result.get("paging", {}).get("cursors", {}).get("after")
        if not result.get("paging", {}).get("next") or not new_after or new_after == after:
            break
        after = new_after
    return videos


def ordered_candidates(videos: list[dict], rotation: dict, rng: random.Random | None = None) -> list[dict]:
    """Favor unused creator collaborations, then unused self-owned videos."""
    rng = rng or random.SystemRandom()
    seen = set(rotation.get("used_ids", []))
    unused_collabs = [v for v in videos if v["id"] not in seen and v.get("source_kind") == "collaboration"]
    unused_own = [v for v in videos if v["id"] not in seen and v.get("source_kind") != "collaboration"]
    used_collabs = [v for v in videos if v["id"] in seen and v.get("source_kind") == "collaboration"]
    used_own = [v for v in videos if v["id"] in seen and v.get("source_kind") != "collaboration"]
    for group in (unused_collabs, unused_own, used_collabs, used_own):
        rng.shuffle(group)
    last = rotation.get("last_id")
    ordered = unused_collabs + unused_own + used_collabs + used_own
    if len(ordered) > 1 and last:
        ordered.sort(key=lambda v: v["id"] == last)
    return ordered


def allowed_video_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "cdninstagram.com" or host.endswith(".cdninstagram.com")
        or host == "fbcdn.net" or host.endswith(".fbcdn.net"))


def download_video(url: str, dest: Path) -> None:
    if not allowed_video_url(url):
        raise ValueError("影片來源不是 Instagram CDN")
    with requests.get(url, stream=True, timeout=(15, 60)) as response:
        response.raise_for_status()
        if not allowed_video_url(response.url):
            raise ValueError("影片轉址不是 Instagram CDN")
        size = 0
        with dest.open("wb") as target:
            for block in response.iter_content(1024 * 1024):
                size += len(block)
                if size > MAX_SOURCE_BYTES:
                    raise ValueError("原影片超過 100 MB")
                target.write(block)
    if size == 0:
        raise ValueError("Instagram 原影片是空檔案")


def duration(path: Path) -> float:
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True, timeout=30)
    return float(proc.stdout.strip())


def encode_story(source: Path, dest: Path) -> None:
    """Preserve the source's picture and soundtrack in a 9:16 Story canvas."""
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0xE8EFF5,setsar=1",
        "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p",
        "-r", "30", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(dest)],
        check=True, timeout=240)
    if dest.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("轉檔後影片超過 100 MB")


def target_time() -> None:
    if os.getenv("GITHUB_EVENT_NAME") == "schedule" or os.getenv("SCHEDULED_DISPATCH") == "true":
        target = dt.datetime.combine(dt.datetime.now(TZ).date(), dt.time(16), TZ)
        seconds = (target - dt.datetime.now(TZ)).total_seconds()
        if 0 < seconds <= 1200:
            time.sleep(seconds)


def prepare() -> None:
    target_time()
    day = dt.datetime.now(TZ).date().isoformat()
    state_path = f"state/video-story-{day}.json"
    output = Path("out")
    output.mkdir(exist_ok=True)
    step_output = Path(os.getenv("GITHUB_OUTPUT", "out/video-step-output.txt"))
    rotation = json_file(ROTATION) or {}
    if os.getenv("DRY_RUN") != "true":
        rotation = reconcile_rotation(rotation, dt.date.fromisoformat(day))
    if json_file(state_path):
        print("今日影片限動已有發布或待查紀錄，避免重複發布")
        step_output.write_text("publish=false\n")
        return
    videos: list[dict] = []
    collab_token = os.getenv("META_COLLAB_TOKEN")
    if collab_token:
        try:
            videos = list_collaborative_reels(collab_token)
            print(f"可用的網紅協作 Reels：{len(videos)} 支")
        except (requests.RequestException, ValueError, RuntimeError) as error:
            print(f"協作 Reels 讀取失敗：{type(error).__name__}")
            notify(f"【白凝影片限動】{day} 協作 Reels 暫時無法讀取，今日改用自有影片。請檢查 Meta 協作授權。")
    try:
        own = list_videos(account_id())
        collab_ids = {item["id"] for item in videos}
        videos += [item for item in own if item["id"] not in collab_ids]
    except (requests.RequestException, ValueError, RuntimeError) as error:
        print(f"自有影片讀取失敗：{type(error).__name__}")
        if videos:
            notify(f"【白凝影片限動】{day} 自有影片暫時無法讀取，今日改用協作 Reels。")
        else:
            raise
    candidates = ordered_candidates(videos, rotation)
    if not candidates:
        notify(f"【白凝影片限動】{day} 帳號沒有官方 API 可讀取的影片，今日不發布。")
        step_output.write_text("publish=false\n")
        return
    for item in candidates:
        source = output / "source.mp4"
        try:
            download_video(item["media_url"], source)
            seconds = duration(source)
            if not 3 <= seconds <= MAX_DURATION:
                print(f"略過影片 {item['id']}：長度 {seconds:.1f} 秒，不符限動單片長度")
                continue
            dest = output / "story.mp4"
            encode_story(source, dest)
            content = dest.read_bytes()
            video_path = f"story/video-{day}_{hashlib.sha256(content).hexdigest()[:12]}.mp4"
            page_file = Path("site") / video_path
            page_file.parent.mkdir(parents=True, exist_ok=True)
            page_file.write_bytes(content)
            (output / "video-manifest.json").write_text(json.dumps({"source_id": item["id"],
                "source_permalink": item.get("permalink", ""), "path": video_path,
                "size": len(content), "date": day, "source_kind": item.get("source_kind", "own"),
                "available_ids": [v["id"] for v in videos]}, ensure_ascii=False))
            step_output.write_text("publish=true\n")
            print(f"已準備影片 {item['id']}，長度 {seconds:.1f} 秒")
            return
        except (requests.RequestException, subprocess.SubprocessError, OSError) as error:
            print(f"略過影片 {item['id']}：{type(error).__name__}")
        except ValueError as error:
            print(f"略過影片 {item['id']}：{type(error).__name__}")
        finally:
            source.unlink(missing_ok=True)
    notify(f"【白凝影片限動】{day} 找不到可轉成限動的既有影片（可能是長度、授權或檔案限制），今日不發布。")
    step_output.write_text("publish=false\n")


def publish() -> None:
    manifest = json.loads(Path("out/video-manifest.json").read_text())
    day = manifest["date"]
    if dt.datetime.now(TZ).date().isoformat() != day:
        raise RuntimeError("已跨日，停止發布避免輪播紀錄錯位")
    state_path = f"state/video-story-{day}.json"
    if json_file(state_path):
        raise RuntimeError("今日影片限動已有發布或待查紀錄")
    url = public_video_url(manifest["path"], manifest["size"])
    gh_write(state_path, json.dumps({"status": "pending", "source_id": manifest["source_id"],
        "source_permalink": manifest["source_permalink"], "source_kind": manifest.get("source_kind", "own"),
        "available_ids": manifest["available_ids"]}, ensure_ascii=False).encode(),
        f"Mark video Story pending {day}")
    media_id = publish_story(url)
    gh_write(state_path, json.dumps({"status": "published", "source_id": manifest["source_id"],
        "source_permalink": manifest["source_permalink"], "source_kind": manifest.get("source_kind", "own"),
        "media_id": media_id,
        "available_ids": manifest["available_ids"]}, ensure_ascii=False).encode(),
        f"Mark video Story published {day}")
    rotation = json_file(ROTATION) or {}
    rotation = update_rotation(rotation, manifest["source_id"], manifest["available_ids"], day)
    gh_write(ROTATION, json.dumps(rotation, ensure_ascii=False).encode(),
        f"Rotate video Story {day}")
    source_label = "網紅協作 Reel" if manifest.get("source_kind") == "collaboration" else "既有影片"
    notify(f"【白凝影片限動】{day} 已將{source_label}發布為直接播放的限動：{manifest['source_permalink']}")


if __name__ == "__main__":
    try:
        {"prepare": prepare, "publish": publish}[sys.argv[1]]()
    except Exception as error:
        try:
            notify(f"【白凝影片限動】今日自動發布失敗，請檢查 GitHub Actions。原因：{str(error)[:300]}")
        finally:
            raise
