# 白凝每日限動

依可預約時段產生 Instagram 限動圖片與含原創純音樂的短片。正式發布前會再次核對時段。

自 2026-10-15（台北時間）起，桌面攝影版與原版依日期逐日交替：10/15 桌面版、10/16 原版、10/17 桌面版，依此循環。兩版都呈現未來 21 天內最近三個有空檔的日期，發布前重新核對行事曆；若未來 21 天皆無空檔才跳過當日發布，版型輪替仍按日期推進。配樂維持三首日系原創純音樂輪播。

此公開儲存庫保存排版程式與示意素材，不應提交帳密或顧客資料。

版型示意：[圖片](sample/story.jpg)／[影片](sample/story.mp4)。示意日期不代表即時可預約時段。

## 下午既有影片限動

另一個 GitHub Actions 排程在台北時間每日約 16:00，從 @wntw_shida 官方 API 可讀取的既有影片隨機選一支，轉成直式影片限動並直接播放。先選尚未發布過的影片，輪播一圈後重選；若影片超過單則限動的 60 秒、超過 100 MB、無官方可讀取的影片網址，或轉檔失敗，會跳過該片。若當日都沒有可用影片，會透過 LINE 通知而不發布。此流程不會產生可點回原 Reel 的分享卡。

影片選取及發布狀態保存在 `state/video-story-*.json`，授權資料沿用既有加密權杖。手動執行的 `dry_run` 預設為 true，可驗證影片讀取、轉檔與公開網址部署，且不發布 IG。GitHub Actions 排程可能延遲，16:00 為目標時間，不保證整點上線。

## 準點排程（待 Cloudflare 帳號設定）

GitHub 的原生 `schedule` 在 2026-10-18 至 10-20 三天把早上 08:50 的工作延到台北時間約 13:10–13:22 才開始。`scheduler/` 已備妥 Cloudflare Worker Cron：UTC 00:58 與 07:58 分別觸發早上時段限動、下午既有影片限動。Worker 只呼叫 GitHub 的 `workflow_dispatch`，影片渲染與 IG 發布仍在既有 GitHub Actions 內執行。若工作提早開始，程式會等到台北時間 09:00 或 16:00。GitHub 原生排程保留備援；每日狀態檢查與共用 concurrency group 防止重複發布。

啟用需在 Cloudflare 帳號部署 `scheduler/wrangler.toml` 與 `worker.mjs`，並把僅限此儲存庫、Repository `Actions: write` 的 GitHub fine-grained token 設為 Worker Secret `GITHUB_DISPATCH_TOKEN`。不要把 token 寫進程式、儲存庫或聊天。部署後先以測試方式確認兩個 `workflow_dispatch` 都能啟動，接著驗證首次正式排程及 IG 狀態。Cloudflare Cron 也不保證精確到秒；此配置的目的在降低 GitHub 原生排程出現的數小時延遲。
