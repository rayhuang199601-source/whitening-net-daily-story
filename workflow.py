"""GitHub Actions 的雲端入口；所有密鑰只能從環境變數取得。"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests
from cryptography.fernet import Fernet

from story import TZ, choose_slots, fetch_events, render, video

TIMEOUT = 30
TOKEN_STATE = "state/meta-token.json"
_meta_token: str | None = None


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"缺少環境變數 {name}")
    return value


def notify(message: str) -> None:
    token = os.getenv("LINE_CHANNEL_TOKEN")
    owner = os.getenv("LINE_OWNER_USER_ID")
    if not token or not owner:
        print("LINE 通知未設定：" + message)
        return
    response = requests.post("https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {token}"},
        json={"to": owner, "messages": [{"type": "text", "text": message}]}, timeout=TIMEOUT)
    response.raise_for_status()


def gh_file(path: str) -> dict | None:
    repo = required("GITHUB_REPOSITORY")
    branch = os.getenv("GH_STATE_BRANCH", "main")
    response = requests.get(f"https://api.github.com/repos/{repo}/contents/{path}",
        headers={"Authorization": f"Bearer {required('GITHUB_TOKEN')}", "Accept": "application/vnd.github+json"},
        params={"ref": branch}, timeout=TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def gh_write(path: str, data: bytes, message: str) -> None:
    repo = required("GITHUB_REPOSITORY")
    branch = os.getenv("GH_STATE_BRANCH", "main")
    old = gh_file(path)
    payload = {"message": message, "content": base64.b64encode(data).decode(), "branch": branch}
    if old:
        payload["sha"] = old["sha"]
    response = requests.put(f"https://api.github.com/repos/{repo}/contents/{path}",
        headers={"Authorization": f"Bearer {required('GITHUB_TOKEN')}", "Accept": "application/vnd.github+json"},
        json=payload, timeout=60)
    response.raise_for_status()


def meta_token() -> str:
    """從加密的續期紀錄讀取權杖；首次執行才讀 GitHub Secret。"""
    global _meta_token
    if _meta_token:
        return _meta_token
    saved = gh_file(TOKEN_STATE)
    if saved:
        record = json.loads(base64.b64decode(saved["content"]))
        _meta_token = token_cipher().decrypt(
            record["ciphertext"].encode()).decode()
    else:
        _meta_token = required("META_IG_ACCESS_TOKEN")
    return _meta_token


def token_cipher() -> Fernet:
    """以首次權杖作為加密種子；種子只存在 GitHub Secret。"""
    seed = required("META_IG_ACCESS_TOKEN").encode()
    key = hashlib.sha256(b"whitening-net-ig-token-store-v1\0" + seed).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def refresh_meta_token() -> None:
    """每週續期一次；即使沒有可預約時段也維持權杖有效。"""
    global _meta_token
    saved = gh_file(TOKEN_STATE)
    now = dt.datetime.now(dt.timezone.utc)
    if saved:
        record = json.loads(base64.b64decode(saved["content"]))
        last = dt.datetime.fromisoformat(record["refreshed_at"])
        if now - last < dt.timedelta(days=7):
            return
    else:
        record = None
    current = meta_token()
    if record:
        response = requests.get("https://graph.instagram.com/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": current}, timeout=TIMEOUT)
        if not response.ok:
            raise RuntimeError(f"Instagram 權杖續期失敗（HTTP {response.status_code}）")
        result = response.json()
        if int(result.get("expires_in", 0)) < 30 * 86400 or not result.get("access_token"):
            raise RuntimeError("Instagram 權杖續期結果無效")
        current = result["access_token"]
    encrypted = token_cipher().encrypt(current.encode()).decode()
    gh_write(TOKEN_STATE, json.dumps({"ciphertext": encrypted, "refreshed_at": now.isoformat()}).encode(),
             "Refresh encrypted Instagram access token")
    _meta_token = current


def public_video_url(path: str, expected_size: int) -> str:
    url = required("PAGES_BASE_URL").rstrip("/") + "/" + path
    for _ in range(36):
        try:
            response = requests.get(url, headers={"Range": "bytes=0-0"}, timeout=15)
            if response.status_code in (200, 206) and response.headers.get("content-type", "").startswith("video/"):
                total = response.headers.get("content-range", "").split("/")[-1]
                if total == str(expected_size) or response.headers.get("content-length") == str(expected_size):
                    return url
        except requests.RequestException:
            pass
        time.sleep(10)
    raise RuntimeError("公開影片網址未在六分鐘內更新；停止發布")


def graph(method: str, path: str, *, data=None, params=None) -> dict:
    version = os.getenv("META_API_VERSION", "v26.0")
    response = requests.request(method, f"https://graph.instagram.com/{version}/{path}",
        headers={"Authorization": f"Bearer {meta_token()}"},
        data=data, params=params, timeout=TIMEOUT)
    if not response.ok:
        detail = response.text.replace(meta_token(), "[REDACTED]")[:400]
        raise RuntimeError(f"Meta API {response.status_code}: {detail}")
    return response.json()


def publish_story(url: str) -> str:
    user = required("META_IG_USER_ID")
    container = graph("POST", f"{user}/media", data={"media_type": "STORIES", "video_url": url})["id"]
    for _ in range(30):
        status = graph("GET", container, params={"fields": "status_code,status"})
        if status.get("status_code") == "FINISHED":
            return graph("POST", f"{user}/media_publish", data={"creation_id": container})["id"]
        if status.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError("Meta 限動容器處理失敗：" + status.get("status", ""))
        time.sleep(10)
    raise RuntimeError("Meta 限動影片處理逾時；請檢查容器 " + container)


def prepare() -> None:
    if os.getenv("GITHUB_EVENT_NAME") == "schedule":
        target = dt.datetime.combine(dt.datetime.now(TZ).date(), dt.time(9), TZ)
        wait = (target - dt.datetime.now(TZ)).total_seconds()
        if 0 < wait <= 900:
            time.sleep(wait)
    now = dt.datetime.now(TZ)
    if os.getenv("DRY_RUN") != "true":
        refresh_meta_token()
    day = now.date().isoformat()
    state_path = f"state/{day}.json"
    step_output = Path(os.getenv("GITHUB_OUTPUT", "out/step-output.txt"))
    step_output.parent.mkdir(parents=True, exist_ok=True)
    if gh_file(state_path):
        print("本日已有發布紀錄或待查狀態，避免重複發布")
        step_output.write_text("publish=false\n")
        return
    slots = choose_slots(fetch_events(now), now)
    if not slots:
        notify(f"【白凝限動】{day} 未來 21 天皆無可預約時段，今日不發布。")
        step_output.write_text("publish=false\n")
        return
    output = Path("out")
    output.mkdir(exist_ok=True)
    render(slots, output / "story.jpg")
    video(output / "story.jpg", output / "story.mp4")
    content = (output / "story.mp4").read_bytes()
    video_path = f"story/{day}_{hashlib.sha256(content).hexdigest()[:12]}.mp4"
    destination = Path("site") / video_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    (output / "manifest.json").write_text(json.dumps({"slots": slots, "path": video_path, "size": len(content)}, ensure_ascii=False))
    step_output.write_text("publish=true\n")


def publish() -> None:
    manifest = json.loads(Path("out/manifest.json").read_text())
    now = dt.datetime.now(TZ)
    day = now.date().isoformat()
    slots = choose_slots(fetch_events(now), now)
    if slots != manifest["slots"]:
        notify(f"【白凝限動】{day} 發布前空檔已變更，今日不發布，避免刊出過期時段。")
        return
    url = public_video_url(manifest["path"], manifest["size"])
    state_path = f"state/{day}.json"
    # 先記「待查」，中斷後重跑也不會重複發布；失敗需人工查核帳號狀態。
    gh_write(state_path, json.dumps({"status": "pending", "slots": slots, "video": url}, ensure_ascii=False).encode(),
             f"Mark White Ning Story pending {day}")
    media_id = publish_story(url)
    gh_write(state_path, json.dumps({"status": "published", "slots": slots, "media_id": media_id}, ensure_ascii=False).encode(),
             f"Mark White Ning Story published {day}")
    notify(f"【白凝限動】{day} 已發布至 @wntw_shida，限動媒體 ID：{media_id}。")


if __name__ == "__main__":
    try:
        {"prepare": prepare, "publish": publish}[sys.argv[1]]()
    except Exception as error:
        try:
            notify(f"【白凝限動】今日自動發布失敗，請檢查 GitHub Actions。原因：{str(error)[:300]}")
        finally:
            raise
