# 白凝每日限動

依可預約時段產生 Instagram 限動圖片與含原創純音樂的短片。正式發布前會再次核對時段。

自 2026-10-15（台北時間）起，桌面攝影版與原版依日期逐日交替：10/15 桌面版、10/16 原版、10/17 桌面版，依此循環。兩版都呈現未來 21 天內最近三個有空檔的日期，發布前重新核對行事曆；若未來 21 天皆無空檔才跳過當日發布，版型輪替仍按日期推進。配樂維持三首日系原創純音樂輪播。

此公開儲存庫保存排版程式與示意素材，不應提交帳密或未加密的顧客資料。

## 中午齒色對比限動

自 2026-10-24 起，台北時間每日 12:00 發布一張齒色前後對比限動。8 張依日期輪播，10/24 發第 1 張、10/25 發第 2 張，第 8 張後回到第 1 張；同日有發布或待查紀錄時不重複發布。每張轉成 8 秒影片，沿用三首已核准的日系純音樂輪播。

原圖只保存在白凝事業部工作資料夾；公開儲存庫的 `assets/ba_story/` 僅保存加密圖片。GitHub Actions 以 `BA_IMAGE_KEY` Secret 解密當日圖片後，透過 Pages 公開影片供 Instagram 讀取。影片會留在 Pages，直到下一次成功部署替換。不要提交 `.env` 或解密後的圖片。限動畫面會引導觀眾到 IG 個人檔案的官方 LINE 連結；自動發布無法加入可點擊的 IG 原生連結貼圖。

正式排程：`.github/workflows/ba-story.yml` 的 GitHub cron 在台北 11:50 觸發，程式在提早開始時等到 12:00；製片、部署和 Meta 處理仍需時間，因此實際上線約在中午。`scheduler/` 的 Cloudflare cron 在台北 11:58 觸發同一個 workflow，以降低 GitHub 原生排程的延誤。兩者共用防重複發布檢查。首次啟用前，需確認 `BA_IMAGE_KEY` Secret、Cloudflare 的 GitHub dispatch Secret 與三組 cron 已設定。乾跑會驗證解密、製片、Pages 公開網址，但不發布 IG。

`state/ba-story-日期.json` 若為 `pending`，表示發送結果待查。請先到 IG 查是否已發，再決定如何處理；不可直接刪除狀態檔重跑，以免重複發布。

版型示意：[圖片](sample/story.jpg)／[影片](sample/story.mp4)。示意日期不代表即時可預約時段。

## 下午既有影片限動

另一個 GitHub Actions 排程在台北時間每日約 16:00，從 @wntw_shida 官方 API 可讀取的既有影片隨機選一支，轉成直式影片限動並直接播放。先選尚未發布過的影片，輪播一圈後重選；若影片超過單則限動的 60 秒、超過 100 MB、無官方可讀取的影片網址，或轉檔失敗，會跳過該片。若當日都沒有可用影片，會透過 LINE 通知而不發布。此流程不會產生可點回原 Reel 的分享卡。

影片選取及發布狀態保存在 `state/video-story-*.json`，授權資料沿用既有加密權杖。手動執行的 `dry_run` 預設為 true，可驗證影片讀取、轉檔與公開網址部署，且不發布 IG。GitHub Actions 排程可能延遲，16:00 為目標時間，不保證整點上線。

## 準點排程（待 Cloudflare 帳號設定）

GitHub 的原生 `schedule` 在 2026-10-18 至 10-20 三天把早上 08:50 的工作延到台北時間約 13:10–13:22 才開始。`scheduler/` 已備妥 Cloudflare Worker Cron：UTC 00:58、03:58 與 07:58 分別觸發早上時段、齒色對比、下午影片限動。Worker 呼叫 GitHub 的 `workflow_dispatch`，影片渲染與 IG 發布仍在既有 GitHub Actions 內執行。提早開始的工作會等到台北時間 09:00、12:00 或 16:00。GitHub 原生排程保留備援；各類限動由每日狀態檔防止重複發布，公開影片網址與檔案大小會在 Meta 發布前再次核對。

啟用需在 Cloudflare 帳號部署 `scheduler/wrangler.toml` 與 `worker.mjs`，並把僅限此儲存庫、Repository `Actions: write` 的 GitHub fine-grained token 設為 Worker Secret `GITHUB_DISPATCH_TOKEN`。不要把 token 寫進程式、儲存庫或聊天。部署後先以測試方式確認三個 `workflow_dispatch` 都能啟動，接著驗證首次正式排程及 IG 狀態。Cloudflare Cron 也不保證精確到秒；此配置的目的在降低 GitHub 原生排程出現的數小時延遲。
