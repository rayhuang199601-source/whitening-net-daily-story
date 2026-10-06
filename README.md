# 白凝每日雲端限動發布流程

## 目前狀態（2026-10-06）

程式、版型、純音樂與本機預覽已完成；**尚未部署，排程未啟用**。缺少 Meta 發布憑證、Google 行事曆專用讀取授權與雲端儲存庫。此資料夾沒有任何帳密。

預覽：[sample/story.jpg](sample/story.jpg)、[sample/story.mp4](sample/story.mp4)。預覽中的時段僅供版型測試，不能當作即時空檔發布。

## 每日行為

1. GitHub Actions 在台北時間 08:50（UTC 00:50）觸發，程式等到 09:00 才讀取行事曆。GitHub 排程可能延遲，不能保證整點準時。
2. 只讀取 Google 行事曆「白凝師大店 預約」。沿用 `DailySlotPush.gs` 的規則：標題完全等於 `牙齒淨白_可預約`、連續一小時完整覆蓋、同一本行事曆其他事件不衝突；往後最多看 21 天，選 3 個**有時段**的日期。
3. 若完全沒有時段：不發布，傳 LINE 通知 Ray。
4. 產生 1080×1920 限動圖片與 8 秒 H.264/AAC 影片。背景音樂為程式自行合成的柔和明亮純音樂，不使用第三方錄音。
5. 透過 GitHub Pages 暫存公開影片，發布前再讀行事曆。若空檔已變更，當天跳過並通知 Ray，避免刊出過期時段。
6. 透過 Meta Graph API 發布至 `@wntw_shida` 的 IG 限動，成功後傳 LINE 通知。先寫入 `pending` 狀態，再送出，避免失敗重跑造成重複發布；`pending` 需人工核查。

## 啟用前的帳號設定

以下均涉及新授權或對外部署，需 Ray 核准後才執行。

1. 建一個**專用公開 GitHub 儲存庫**，只放本資料夾的程式、字型與 Actions 設定；不放顧客資料、憑證或當日預約事件。GitHub Pages 設定為 GitHub Actions 來源。影片網址會公開，因限動本來就是公開內容，並供 Meta 抓取。工作流程內容也會公開。
2. 在 Google Cloud 建立專用 service account，只把「白凝師大店 預約」行事曆以「查看所有活動詳細資訊」授權給該服務帳號。服務帳號 JSON 存入 GitHub Actions secret `GOOGLE_SERVICE_ACCOUNT_JSON`，不寫進程式與 Git。
3. 在 Meta for Developers 建立 App，取得 `@wntw_shida` 商業帳號發布所需的權限與 Page access token。必要權限依 Meta 當前審核結果確認，至少包括 `instagram_basic`、`instagram_content_publish`、`pages_show_list`、`pages_read_engagement`。把 token 存 GitHub Actions secret `META_PAGE_ACCESS_TOKEN`；把 IG user ID 設為 variable `META_IG_USER_ID`。任何登入、條款或新權限授予，由 Ray 審核。
4. 將現有白凝 LINE channel token 與 Ray 個人 LINE user ID 分別放入 Secrets `LINE_CHANNEL_TOKEN`、`LINE_OWNER_USER_ID`，只用於成功、無空檔、失敗通知。若不授權 LINE，應先改用其他通知管道，不能啟用「無空檔通知」承諾。
5. 先透過 `workflow_dispatch` 在非 09:00 時間測試一次，核對可預約時段、影片、音樂、Meta 媒體 ID 與 IG 帳號頁。確認後才保留每日排程。

## 安全與維護

- 不會讀取或發布顧客姓名、電話；影片與通知只含可預約時段。
- GitHub Pages 每日部署會替換前一天的影片。限動本身發布後仍在 IG 保留 24 小時。
- Meta token 失效、權限變更、Pages 部署失敗會中止發布並通知；若 LINE token 也失效，GitHub Actions 的執行紀錄仍會顯示失敗。
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
- [Meta 商業帳號音樂使用說明](https://www.facebook.com/help/instagram/402084904469945)
- [GitHub Actions 排程說明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
