# LINE Bot 智慧名片管家 ── 擁抱 Vertex AI ADK Tools

這是一個基於 **FastAPI**、**Google Cloud Vertex AI**、**Agent Development Kit (ADK)** 以及 **Firebase (Realtime Database & Cloud Storage)** 打造的企業級 LINE 智慧名片管理助理。

本專案採用最新的 AI Agent 代理人架構，利用**動態閉包 (Closures) 技術**，安全地為每位 LINE 使用者綁定專屬的資料庫操作工具（Tools）。大模型能根據使用者的自然語言輸入，自主進行多步驟決策，實現名片查詢、即時欄位編輯與備忘錄修改，並融合 **LINE Flex Message** 提供極致精美的視覺化回覆！

<img width="453" height="638" alt="名片助理主介面" src="https://github.com/user-attachments/assets/918c5b9a-c114-4f1d-b003-cdceaccaf01c" />
<img width="401" height="690" alt="vCard 匯入聯絡人" src="https://github.com/user-attachments/assets/2cb92c49-09da-4f84-80ed-c5463866a513" />

---

## ✨ 核心特色與功能

### 1. 📸 智慧名片掃描與 OCR 結構化
* 傳送任何名片圖片，Bot 將自動調用 Vertex AI 多模態模型（`gemini-3-flash-preview` / `gemini-1.5-flash`）進行高精度視覺分析。
* 自動提取**姓名、職稱、公司、地址、電話、Email** 等欄位並轉化為結構化 JSON 資料，隨後安全地儲存至您的 Firebase 資料庫。

### 2. 🤖 Vertex AI ADK 智慧 Agent
* 導入 Google 官方最新的 **Agent Development Kit (ADK)** 框架。
* 透過**動態閉包 (Closures)** 技術在對話生命週期中動態生成 Tools。這不僅保障了使用者的資料隱私（使用者 A 絕對無法存取使用者 B 的名片），還能在模型思考期間完美收集「想要呈現給使用者的所有名片 ID」。

### 3. 💬 全自然語言名片管理
* 支援多輪自然語言對話操作。您可以用最直覺的中文命令：
  * *「幫我查王大明的電話是多少？」*
  * *「幫我把大明公司的地址改成信義路五段1號」*
  * *「幫我把這張名片加上『下週一開會』的備忘錄」*
* Agent 將自主判斷並連續調用 `get_all_namecards` -> 尋找對應 `card_id` -> 執行 `update_namecard_field` / `update_namecard_memo` -> 調用 `display_namecard` 將更新後的精美 Flex Message 呈現在 LINE 視窗中！

### 4. 🛡️ 生產級本機關鍵字備援搜尋 (Local Fallback)
* 為了確保高可用性（SLA），當 Vertex AI API 達到配額限制、遭遇網路超時或故障時，Webhook 會**自動無縫降級**為本機 Firebase 關鍵字搜尋模式。
* 依然能夠精準抓取相符的名片並以 Flex Message 卡片回傳，提供 100% 不中斷的優雅使用者體驗。

### 5. 📥 一鍵產出 QR Code 匯入手機通訊錄
* 點擊卡片上的「📥 加入通訊錄」按鈕，系統會提取 Firebase 內名片資料，自動生成符合 **vCard 3.0** 國際標準協定的字串。
* 將其編碼為高解晰度 QR Code 圖片並上傳至 Firebase Storage (`qrcodes/{user_id}/{card_id}.png`)，提供 HTTPS 公開 URL。
* 使用者只需使用手機相機掃描，即可一秒將聯絡人匯入 iPhone 或 Android 本機通訊錄，免去手動輸入的痛苦！

### 6. 📊 快捷選單與便利指令
* 支援 LINE 內建 Quick Replies 快捷按鈕：
  * **📊 統計**：即時查看資料庫名片總數、本月新增數量以及最常合作的公司。
  * **📋 列表**：快速得知目前已儲存的聯絡人總量。
  * **🧪 測試**：一鍵產生精美的模擬測試名片卡片。
  * **ℹ️ 說明**：取得最完整的操作功能導覽。
* **重複清理**：輸入關鍵字 `remove`，系統將自動比對並清除擁有重複 Email 的名片。

---

## 🛠️ 技術架構

```
                     ┌──────────────────┐
                     │     LINE App     │
                     └────────┬─────────┘
                              │ (HTTPS Webhook)
                              ▼
                 ┌──────────────────────────┐
                 │ FastAPI App on Cloud Run │
                 └──────┬────────────┬──────┘
                        │            │
      ┌─────────────────┘            └─────────────────┐
      ▼ (Vertex AI & ADK)                              ▼ (Firebase Admin SDK)
┌───────────────────────────┐                ┌──────────────────────────┐
│   ADK Agent & Runner      │                │   Firebase Database      │
├─ gemini-3-flash-preview   │                ├─ Realtime DB (名片資料)  │
├─ Dynamic Closure Tools    │                └─ Storage (vCard QR Code) │
│  (DB CRUD Operations)     │                └──────────────────────────┘
└───────────────────────────┘
```

---

## 🚀 部署至 Google Cloud Run (極致簡化版)

本專案已完全容器化並適配 **Google Cloud Run**。我們強烈推薦使用 **IAM 角色免 Key 認證**（Application Default Credentials），這能讓您在完全不需要配置繁瑣的 JSON 密鑰環境變數下，完成極速且安全的部署。

### 1. 事前準備
1. 擁有一個已啟用帳單的 [Google Cloud 專案](https://console.cloud.google.com/)。
2. 啟用專案中的 **Vertex AI API** 與 **Cloud Build API**。
3. 建立一個 [Firebase 專案](https://console.firebase.google.com/)，並啟用 **Realtime Database** 與 **Cloud Storage**。
4. 取得 LINE Bot 的 **Channel Secret** 與 **Channel Access Token**。

### 2. 極速單指令部署 (Cloud Run Source Deploy)
您甚至不需要手動打包 Docker Image。在專案根目錄下執行以下指令，GCP 將自動完成程式碼上傳、建置並完成服務部署：

```bash
# 請將以下變數替換為您自己的設定值
gcloud run deploy linebot-namecard-python \
  --source . \
  --platform managed \
  --region asia-east1 \
  --allow-unauthenticated \
  --set-env-vars "ChannelSecret=YOUR_LINE_CHANNEL_SECRET,\
ChannelAccessToken=YOUR_LINE_CHANNEL_ACCESS_TOKEN,\
PROJECT_ID=YOUR_GCP_PROJECT_ID,\
FIREBASE_URL=https://YOUR_PROJECT_ID-default-rtdb.firebaseio.com/,\
FIREBASE_STORAGE_BUCKET=YOUR_PROJECT_ID.appspot.com"
```

> [!TIP]
> 部署完成後，GCP 控制台會輸出一個服務網址（Service URL），例如 `https://linebot-namecard-xxxxxx-de.a.run.app`。請將此網址貼回 LINE Developers Console 的 **Webhook URL** 設定中（別忘了在網址最後方加上斜線 `/`）。

### 3. IAM 權限設定 (免環境變數認證，強烈推薦！)
為了讓部署在 Cloud Run 上的應用程式能夠直接讀寫 Firebase Realtime Database / Storage，並呼叫 Vertex AI 服務，您只需要為 **Cloud Run 的執行服務帳戶**（預設通常是 `Compute Engine default service account` 或您自訂的 Service Account）在 IAM 主控台中賦予以下三個角色：

1. **Vertex AI 使用者** (`roles/aiplatform.user`)：讓 ADK 與 Gemini 能夠執行生成。
2. **Firebase Realtime Database 管理員** (`roles/firebasedatabase.admin`)：允許讀寫 RTDB。
3. **Storage 管理員** (`roles/storage.admin`)：用於將 vCard QR Code 寫入 Storage。

設定完成後，Cloud Run 會自動透過 `credentials.ApplicationDefault()` 進行安全的身分驗證，**無需額外設定任何 `GOOGLE_APPLICATION_CREDENTIALS` 檔案或 JSON 環境變數**！

---

### 💡 備援方案：本機測試或跨平台部署 (使用 JSON Key)
如果您是在本機開發、或是將專案部署在 GCP 之外的平台（例如 Heroku, Render 等），無法使用 IAM 服務帳戶認證時：
1. 請至 Firebase 專案設定 -> `服務帳戶`，點擊「產生新的私密金鑰」並下載 JSON 檔案。
2. 將該 JSON 檔案的內容壓縮並轉換為單行字串。
3. 在部署或啟動環境中，加入環境變數 `GOOGLE_APPLICATION_CREDENTIALS_JSON`，並貼入該 JSON 字串。系統會自動從此環境變數中讀取並初始化 Firebase。

---

## 💻 本機開發與執行

### 1. 安裝相依套件
建議使用 Python 3.10 或以上版本。在專案根目錄下執行：
```bash
pip install -r requirements.txt
```

### 2. 設定環境變數
在本機開發時，請設定對應的環境變數。您可以建立一個啟動指令檔或在 Shell 中匯入：
```bash
export ChannelSecret="YOUR_SECRET"
export ChannelAccessToken="YOUR_TOKEN"
export PROJECT_ID="YOUR_GCP_PROJECT_ID"
export FIREBASE_URL="https://YOUR_PROJECT_ID-default-rtdb.firebaseio.com/"
export FIREBASE_STORAGE_BUCKET="YOUR_PROJECT_ID.appspot.com"

# 本機開發必備：指定服務帳戶金鑰路徑以進行驗證
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account.json"
```

### 3. 啟動本機伺服器
使用 Uvicorn 啟動 FastAPI 服務：
```bash
uvicorn app.main:app --reload --port 8080
```

### 4. 本機 Webhook 測試
使用 [ngrok](https://ngrok.com/) 或 `cloudflared` 將本機的 8080 端口對外曝露，並將產生的 HTTPS 網址設定至 LINE Developers Console 進行測試：
```bash
ngrok http 8080
```

---

## 📜 授權條款 (License)

本專案採用 **MIT License** 授權。詳細資訊請參考 `LICENSE` 檔案。
