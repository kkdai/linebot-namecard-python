# LineBot Smart Namecard

這是一個使用 FastAPI 和 LINE Messaging API 的智能名片管理機器人。該機器人可以處理文本和圖像消息，並將名片數據存儲在 Firebase Firestore 中。

## 功能

- 接收並處理文本消息
- 接收並處理圖像消息，從圖像中提取名片數據
- 將名片數據存儲在 Firebase Firestore 中
- 查詢和刪除冗餘的名片數據

## 環境變數

在運行此應用程序之前，請確保設置以下環境變數：

- `ChannelSecret`: LINE Messaging API 的 Channel Secret
- `ChannelAccessToken`: LINE Messaging API 的 Channel Access Token
- `GEMINI_API_KEY`: Gemini API 的 API Key

## 安裝

1. 克隆此存儲庫：

    ```bash
    git clone https://github.com/yourusername/linebot-smart-namecard.git
    cd linebot-smart-namecard
    ```

2. 創建並激活虛擬環境：

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. 安裝依賴項：

    ```bash
    pip install -r requirements.txt
    ```

4. 設置環境變數：

    ```bash
    export ChannelSecret=your_channel_secret
    export ChannelAccessToken=your_channel_access_token
    export GEMINI_API_KEY=your_gemini_api_key
    ```

5. 運行應用程序：

    ```bash
    uvicorn main:app --reload
    ```

## 使用

### 接收文本消息

- 發送 "test" 消息以生成並返回示例名片數據。
- 發送 "list" 消息以列出所有名片數據。
- 發送 "remove" 消息以刪除冗餘的名片數據。

### 接收圖像消息

- 發送包含名片圖像的消息，機器人將提取名片數據並將其存儲在 Firebase Firestore 中。

## 代碼結構

- `main.py`: 主應用程序文件，包含所有的路由和處理邏輯。
- `requirements.txt`: 依賴項文件。

## Contributing

If you'd like to contribute to this project, please feel free to submit a pull request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
