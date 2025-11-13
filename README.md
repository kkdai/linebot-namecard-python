# LINE Bot 智慧名片管家

這是一個使用 FastAPI、Firebase Realtime Database 以及 Gemini Pro API 打造的 LINE Bot 應用程式。這個機器人可以接收並處理文字與圖片訊息，從名片圖片中解析出聯絡人資訊，並將其儲存到 Firebase 中方便管理與查詢。

<img width="453" height="638" alt="Microsoft PowerPoint 2025-08-01 18 39 19" src="https://github.com/user-attachments/assets/918c5b9a-c114-4f1d-b003-cdceaccaf01c" />

<img width="401" height="690" alt="image" src="https://github.com/user-attachments/assets/2cb92c49-09da-4f84-80ed-c5463866a513" />


## ✨ 主要功能

*   **智慧名片辨識**：傳送名片圖片，Bot 會使用 Gemini Pro Vision API 自動解析圖片中的姓名、職稱、公司、電話、Email 等資訊，並轉換成結構化資料。
*   **Firebase 資料庫整合**：所有名片資料都會安全地儲存在您的 Firebase Realtime Database 中，方便隨時存取。
*   **互動式資料管理**：
    *   **新增/修改記事**：為每張名片添加備忘錄。
    *   **即時編輯**：如果 AI 辨識有誤，可直接在 LINE 中點擊按鈕修改錯誤的欄位。
    *   **關鍵字查詢**：輸入關鍵字（如公司或姓名）即可快速找到相關名片。
*   **📥 一鍵加入通訊錄**：點擊名片上的「加入通訊錄」按鈕，即可獲得 QR Code，用手機相機掃描後直接匯入聯絡人到手機通訊錄（支援 iPhone/Android）。
*   **簡易指令互動**：
    *   `list`：列出資料庫中所有的名片。
    *   `remove`：清除重複的名片資料。
    *   `test`：產生一張測試用的名片，方便您預覽卡片樣式。

## 🚀 如何部署到 GCP (Google Cloud Platform)

本專案已容器化，推薦使用 [Google Cloud Run](https://cloud.google.com/run) 進行部署，它能提供 Serverless 的彈性與自動擴展能力。

### 部署步驟

1.  **打包成 Docker Image**：
    在您的開發環境中，確保已安裝 Docker。於專案根目錄下，執行以下指令將應用程式打包成一個 Docker image：
    ```bash
    # {PROJECT_ID} 是您的 GCP 專案 ID
    # {IMAGE_NAME} 是您為這個映像檔取的名稱 (例如：linebot-namecard)
    gcloud builds submit --tag gcr.io/{PROJECT_ID}/{IMAGE_NAME}
    ```
    這個指令會使用 GCP Cloud Build 自動打包並將映像檔推送到 Artifact Registry。

2.  **部署到 Cloud Run**：
    映像檔準備好後，執行以下指令將其部署到 Cloud Run：
    ```bash
    gcloud run deploy {IMAGE_NAME} \
      --image gcr.io/{PROJECT_ID}/{IMAGE_NAME} \
      --platform managed \
      --region asia-east1 \
      --allow-unauthenticated \
      --set-env-vars "ChannelSecret=YOUR_CHANNEL_SECRET,ChannelAccessToken=YOUR_CHANNEL_ACCESS_TOKEN,GEMINI_API_KEY=YOUR_GEMINI_API_KEY,FIREBASE_URL=YOUR_FIREBASE_URL,FIREBASE_STORAGE_BUCKET=YOUR_PROJECT_ID.appspot.com,GOOGLE_APPLICATION_CREDENTIALS_JSON=YOUR_FIREBASE_SERVICE_ACCOUNT_JSON"
    ```
    部署成功後，GCP 會提供一個服務網址 (Service URL)，這就是您的 LINE Bot Webhook URL。

### 環境變數說明

在部署時，您需要設定以下幾個環境變數，這是讓 Bot 正常運作的關鍵：

*   `ChannelSecret`：**[必要]** LINE Channel 的 **Channel secret**。您可以在 [LINE Developers Console](https://developers.line.biz/console/) 中找到。
*   `ChannelAccessToken`：**[必要]** LINE Channel 的 **Channel access token**。同樣在 LINE Developers Console 中取得。
*   `GEMINI_API_KEY`：**[必要]** 您的 Google Gemini API 金鑰。您可以從 [Google AI Studio](https://aistudio.google.com/app/apikey) 取得。
*   `FIREBASE_URL`：**[必要]** 您的 Firebase Realtime Database 網址。格式通常是 `https://{your-project-id}-default-rtdb.firebaseio.com/`。
*   `FIREBASE_STORAGE_BUCKET`：**[必要]** 您的 Firebase Storage Bucket 名稱。格式通常是 `{your-project-id}.appspot.com`。用於儲存 QR Code 圖片。請確保 Firebase Storage 已啟用，並且服務帳戶有寫入權限。
*   `GOOGLE_APPLICATION_CREDENTIALS_JSON`：**[必要]** Firebase 服務帳戶的金鑰 (JSON 格式)。
    1.  前往您的 Firebase 專案設定 -> `服務帳戶`。
    2.  點擊「產生新的私密金鑰」並下載 JSON 檔案。
    3.  **請將整個 JSON 檔案的內容複製成一個單行的字串**，並在部署指令中貼上。這是因為 Cloud Run 的環境變數不支援直接上傳檔案。

## 📜 License (授權條款)

本專案採用 **MIT License** 授權。詳細資訊請參考 `LICENSE` 檔案。

## 🤝 如何貢獻 (Contributing)

非常歡迎您為這個專案做出貢獻！如果您有任何改善建議或發現 Bug，請隨時提出 Issue 或發送 Pull Request。

1.  Fork 本專案。
2.  建立您的分支 (`git checkout -b feature/AmazingFeature`)。
3.  提交您的變更 (`git commit -m 'Add some AmazingFeature'`)。
4.  將分支推送到遠端 (`git push origin feature/AmazingFeature`)。
5.  開啟一個 Pull Request。
