# 白凝每日雲端限動發布流程

## 目前狀態（2026-10-07）

程式、版型、純音樂與本機預覽已完成，專用公開儲存庫與 Pages 發布來源已建立。LINE、行事曆 ID、Google 服務帳號 JSON 已加密存入 GitHub Secrets。Google Calendar API 已啟用；專用服務帳號已有「白凝師大店 預約」的查看活動詳細資料權限。2026-10-07 的 GitHub Actions 乾跑成功，已驗證行事曆讀取、產圖、影片與 Pages 部署，沒有發布 IG。Meta App 已建立，`@wntw_shida` 已接受測試邀請，Instagram 帳號 ID 已存入 GitHub variable。**Instagram 權杖尚未產生；每日排程目前已暫停，僅能手動觸發。**此資料夾沒有任何帳密。

預覽：[sample/story.jpg](sample/story.jpg)、[sample/story.mp4](sample/story.mp4)。預覽中的時段僅供版型測試，不能當作即時空檔發布。

## 每日行為

1. GitHub Actions 在台北時間 08:50（UTC 00:50）觸發，程式等到 09:00 才讀取行事曆。GitHub 排程可能延遲，不能保證整點準時。
2. 只讀取 Google 行事曆「白凝師大店 預約」。沿用 `DailySlotPush.gs` 的規則：標題完全等於 `牙齒淨白_可預約`、連續一小時完整覆蓋、同一本行事曆其他事件不衝突；往後最多看 21 天，選 3 個**有時段**的日期。
3. 若完全沒有時段：不發布，傳 LINE 通知 Ray。
4. 產生 1080×1920 限動圖片與 8 秒 H.264/AAC 影片。背景音樂為程式自行合成的柔和明亮純音樂，不使用第三方錄音。
5. 透過 GitHub Pages 暫存公開影片，發布前再讀行事曆。若空檔已變更，當天跳過並通知 Ray，避免刊出過期時段。
6. 透過 Meta Graph API 發布至 `@wntw_shida` 的 IG 限動，成功後傳 LINE 通知。先寫入 `pending` 狀態，再送出，避免失敗重跑造成重複發布；`pending` 需人工核查。

## 啟用前的帳號設定

Ray 已授權建立雲端部署與串接；以下列出完成狀態及啟用前必要步驟。

1. 專用公開 GitHub 儲存庫 [whitening-net-daily-story](https://github.com/rayhuang199601-source/whitening-net-daily-story) 已建立，GitHub Pages 已設定為 GitHub Actions 來源。儲存庫只放本流程的程式與示意預覽；不放顧客資料、憑證或當日預約事件。影片網址會公開，供 Meta 抓取；工作流程內容也會公開。
2. Google Cloud 專用 service account 與行事曆唯讀分享已完成，Calendar API 已啟用。行事曆 ID 與服務帳號 JSON 已分別存入 GitHub Actions secrets `CALENDAR_ID`、`GOOGLE_SERVICE_ACCOUNT_JSON`；金鑰由 Ray 直接貼入 GitHub，未提交到 Git。
3. Meta App `Whitening Net Daily Story` 已建立並綁定白凝商業資產；採用 Instagram 登入 API，只加入 `instagram_business_basic` 與 `instagram_business_content_publish` 兩項權限。`@wntw_shida` 已接受測試邀請，IG user ID 已存入 variable `META_IG_USER_ID`。Meta 預設產生的登入網址要求了額外的私訊、留言和洞察權限，因此改用官方文件允許的自訂 OAuth 網址，只要求上述兩項權限。Ray 需完成 Instagram 登入與授權，並把一次性授權碼存入 GitHub Secret `META_IG_AUTH_CODE`、Instagram 應用程式密鑰存入 `META_IG_APP_SECRET`。接著以 `bootstrap_only` 手動執行一次工作流程，將授權碼換成 60 天權杖並加密保存。完成後可刪除一次性授權碼 Secret。任何登入、條款或新權限授予，由 Ray 審核。
4. 現有白凝 LINE channel token 與 Ray 個人 LINE user ID 已分別放入 Secrets `LINE_CHANNEL_TOKEN`、`LINE_OWNER_USER_ID`，只用於成功、無空檔、失敗通知。
5. 已透過 `workflow_dispatch` 的 `dry_run` 模式驗證行事曆、影片與 Pages。待 Meta 發布憑證完成後，再實測限動發布、媒體 ID 與 IG 帳號頁，確認後才啟用每日排程。

## 安全與維護

- 不會讀取或發布顧客姓名、電話；影片與通知只含可預約時段。
- GitHub Pages 每日部署會替換前一天的影片。限動本身發布後仍在 IG 保留 24 小時。
- Meta token 失效、權限變更、Pages 部署失敗會中止發布並通知；若 LINE token 也失效，GitHub Actions 的執行紀錄仍會顯示失敗。
- Instagram 用戶權杖有效 60 天。工作流程每週在雲端續期，並把權杖以 Instagram 應用程式密鑰衍生的密鑰加密後寫入公開儲存庫的 `state/meta-token.json`；應用程式密鑰只放在 GitHub Secret。若重設該 Secret，先處理已加密的續期紀錄，否則會無法解密。Meta 官方規則是權杖存在至少 24 小時後才能續期。
- `state/YYYY-MM-DD.json` 的 `pending` 表示可能已送出但未確認成功，不要直接刪除重跑；先查看 IG 限動與 Meta 媒體狀態。
- 複製本資料夾內容到儲存庫**根目錄**，讓 `.github/workflows/daily-story.yml` 生效。

## 本機檢查

```sh
python3 -m pip install -r requirements.txt
python3 -m unittest -q test_story.py
python3 story.py --sample --output sample
ffprobe -v error -show_entries stream=codec_name,width,height,sample_rate -show_entries format=duration -of json sample/story.mp4
```

## 官方參考

- [Google Apps Script 排程時間會略有偏移](https://developers.google.com/apps-script/guides/triggers/installable)
- [Google Calendar Events API](https://developers.google.com/calendar/api/v3/reference/events/list)
- [Meta Instagram API 官方 Postman 文件](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
- [Meta 內容發布文件](https://developers.facebook.com/documentation/instagram-platform/content-publishing)
- [Meta Instagram 商家登入與授權碼交換](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/business-login)
- [Meta 商業帳號音樂使用說明](https://www.facebook.com/help/instagram/402084904469945)
- [GitHub Actions 排程說明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
