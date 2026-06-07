---
layout: post
title: "[GCP 實戰] LINE Bot 升級大作戰：擁抱 Vertex AI ADK Tools，實作結構化輸出、消歧義清單與二次確認機制"
description: "紀錄將 LINE 名片助理機器人重構為 Google Cloud Vertex AI ADK 驅動的完整過程，分享如何利用 Gemini Structured Outputs 強制 JSON 輸出、解決 LINE 回覆上限的消歧義清單設計、以及手動部署時環境變數蒸發的搶救實錄。"
category:
- AI
- GCP
tags: ["Google Cloud", "Vertex AI", "ADK", "Structured Outputs", "LINE Bot", "Python", "Cloud Run", "Firebase", "Gcloud"]
---

![image-20260606](../images/image-20260526210750701.png)

# 前情提要

在上一篇中，我們成功地將 LINE 名片助理機器人 (`linebot-namecard-python`) 從 AI Studio API Key 驗證模式，升級為企業級的 **Google Cloud Vertex AI** 機制，徹底擺脫了 429 配額焦慮。

然而，原本名片搜尋與操作的做法非常有侷限性：**我們必須先從 Firebase 抓出該使用者的所有名片，打包成一個巨大的 JSON 陣列，然後硬塞進 prompt 中，要求 Gemini 從中挑選最相關的名片物件回傳**。

這種做法有三大死穴：
1. **Token 浪費**：名片一多，每次搜尋都是對 Token 餘額無情的打擊。
2. **缺乏彈性**：模型只能被動搜尋，沒辦法主動針對細節欄位追問、也沒辦法進行資料更新。
3. **無法連動操作**：如果使用者說「幫我把王大明的電話改掉」，我們得在 Webhook 裡寫一堆複雜的 NLP 判斷和分支。

為了解決這些痛點，我們決定將機器人重構，擁抱 Google Cloud 官方最新推出、強大且代碼友善的 **Agent Development Kit (ADK)**，並在後續引入了 **Structured Outputs**、**消歧義清單**與**修改二次確認**機制！

這篇文章將與大家分享，我們如何將 Firebase 的存取重構為 **ADK Tools**、使用 API 原生的 **Structured Outputs**、解決 LINE 的 reply 限制，以及在手動部署 Cloud Run 時所踩到的頂級血淚深坑！

---

# 架構升級：為什麼選擇 ADK 與 Tools？

**Agent Development Kit (ADK)** 是 Google Cloud 推出的一套 code-first 代理人開發框架。以往我們為了讓大模型能呼叫外部 API，必須手寫落落長的 OpenAPI schema 或複雜的 function-calling 描述；而 ADK 讓這一切簡化成簡單的 Python 函數！

我們為名片 Agent 規劃了五大核心資料操作功能，並以 **Python 函數** 的形式直接註冊為 Agent 的 **Tools**：

1. `get_all_namecards()`：讀取當前使用者所有的名片清單（包含 ID）。
2. `get_namecard_by_id(card_id)`：取得指定名片的詳細內容。
3. `display_namecard(card_id)`：核心工具！當模型比對到符合條件的名片時呼叫，用來告訴 Python 主程式「該在畫面上呈現這張名片了」。
4. `update_namecard_memo(card_id, memo)`：更新名片備忘錄。
5. `update_namecard_field(card_id, field, value)`：直接以自然語言更新名片指定欄位（姓名、電話、Email 等）。

---

# 核心程式碼改寫：動態閉包 Tools 實作

在 Webhook 開發中，最重要的一點是**安全性**。我們絕對不能讓 A 使用者搜尋或修改到 B 使用者的名片。

因此，我們不能實作靜態、全域的 Database Tools。取而代之的是，我們在 `handle_smart_query` 中，透過**閉包 (Closures) 機制**為每次對話請求動態建立專屬的 Tools。

這套寫法不僅能完美綁定使用者的 `user_id`，還能利用閉包中的 `found_card_ids` 列表，完美收集模型在思考決策過程中「想要呈現給使用者看的所有名片 ID」：

```python
def make_adk_tools(user_id: str, found_card_ids: list):
    """為特定使用者動態建立專屬的 Firebase 資料存取與操作工具"""
    def get_all_namecards() -> list[dict]:
        """取得當前使用者在 Firebase 資料庫中所有的名片資料列表。"""
        cards_dict = firebase_utils.get_all_cards(user_id)
        all_cards_list = []
        for card_id, card_data in cards_dict.items():
            card_data_with_id = card_data.copy()
            card_data_with_id['card_id'] = card_id
            all_cards_list.append(card_data_with_id)
        return all_cards_list

    def get_namecard_by_id(card_id: str) -> dict:
        """透過特定的 card_id 取得單張名片的詳細欄位與資料。"""
        return firebase_utils.get_card_by_id(user_id, card_id)

    def display_namecard(card_id: str) -> str:
        """顯示特定名片給使用者看。"""
        if card_id not in found_card_ids:
            found_card_ids.append(card_id)
        return f"已將名片 ID 標記為顯示：{card_id}"

    # 後續會介紹此處的「延遲修改」設計
    def update_namecard_memo(card_id: str, memo: str) -> bool:
        """更新特定名片的備忘錄／記事資訊。"""
        user_states[user_id] = {
            'action': 'pending_update',
            'update_type': 'memo',
            'card_id': card_id,
            'memo': memo
        }
        return True

    def update_namecard_field(card_id: str, field: str, value: str) -> bool:
        """更新特定名片的指定欄位。"""
        user_states[user_id] = {
            'action': 'pending_update',
            'update_type': 'field',
            'card_id': card_id,
            'field': field,
            'value': value
        }
        return True

    return [
        get_all_namecards,
        get_namecard_by_id,
        display_namecard,
        update_namecard_memo,
        update_namecard_field
    ]
```

---

# 全新突破：擁抱 Gemini Structured Outputs 結構化輸出

儘管有了 ADK Tools，我們在最初開發「名片圖片 OCR 解析」時，仍然常被大模型的脾氣搞瘋。

以往的做法是透過 `generation_config={"response_mime_type": "application/json"}` 配合長長的 Prompt，命令 Gemini 只能回傳 JSON 字串，並在程式中手動 parse。但偶爾大模型還是會吐出包含 ` ```json ` 標記的 Markdown，或者漏了某些 Key，導致 Parser 直接報錯閃退。

為了解決這個問題，我們決定全面導入 Vertex AI SDK 最新的 **Structured Outputs (結構化輸出)** 機制！

### 1. 定義名片 Schema

在 `app/gemini_utils.py` 中，我們定義了名片物件的約束 Schema。這能強迫 Gemini 的推理結果完全依循此格式輸出：

```python
NAMECARD_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": {
            "type": "STRING",
            "description": "聯絡人姓名，如果看不出來，請填寫 N/A"
        },
        "title": {
            "type": "STRING",
            "description": "職稱或頭銜，如果看不出來，請填寫 N/A"
        },
        "company": {
            "type": "STRING",
            "description": "公司名稱，如果看不出來，請填寫 N/A"
        },
        "address": {
            "type": "STRING",
            "description": "公司或聯絡地址，如果看不出來，請填寫 N/A"
        },
        "phone": {
            "type": "STRING",
            "description": (
                "電話號碼，格式為 #886-0123-456-789,1234。"
                "沒有分機就忽略 ,1234。如果看不出來，請填寫 N/A"
            )
        },
        "email": {
            "type": "STRING",
            "description": "電子郵件信箱，如果看不出來，請填寫 N/A"
        }
    },
    "required": ["name", "title", "company", "address", "phone", "email"]
}
```

### 2. 在 API 呼叫中啟用

我們只需將 `NAMECARD_SCHEMA` 作為 `response_schema` 傳入 `generation_config`：

```python
def generate_json_from_image(img: PIL.Image.Image, prompt: str) -> object:
    model = GenerativeModel(
        "gemini-3-flash-preview",
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": NAMECARD_SCHEMA
        },
    )
    img_part = Part.from_data(data=pil_to_bytes(img), mime_type="image/jpeg")
    response = model.generate_content([prompt, img_part], stream=False)
    return response
```
有了這項升級，大模型回傳的 JSON 錯誤率直接歸零！我們也可以把原本程式中繁複的 Regex 防錯機制通通丟進垃圾桶。

---

# LINE 限制大踩坑：消歧義清單與二次確認

當系統開始上線測試後，真正的生產環境巨坑才剛要開始。我們在對話邏輯上又撞到了兩個嚴重的問題。

### 踩坑一：搜尋結果過多導致的 LINE 400 報錯

在 LINE Bot 中，我們原本的邏輯是將找到的名片以橫向滑動的 Carousel 卡片呈現。為了防錯，我們對名片數量做了 `found_card_ids[:5]` 的限制，最多回傳 5 張。

然而，我們忽視了 LINE Bot API 的鐵律：**單次回覆 (reply_message) 的訊息氣泡數量必須在 1 到 5 個之間**。
當使用者搜尋「LINE」，系統在 Firebase 裡找到了 5 張相關名片，當我們把這 5 個 Flex Card 卡片，加上最前面 Agent 的 1 個文字對話回覆送出時，總訊息數變成了 **6 個**！結果就是 LINE API 直接無情回傳 `status_code=400 (Size must be between 1 and 5)`，機器人瞬間已讀不回。

#### 💡 解決方案：消歧義清單 (Disambiguation List)

我們將顯示邏輯修改為：
1. 當搜尋結果為 **1 ~ 4 筆**時，直接以 Carousel 顯示名片大卡片（加文字共 2~5 個訊息，完全安全）。
2. 當搜尋結果為 **5 筆以上**時，改為回傳一個**「名片搜尋清單」的 Flex Message Bubble**。清單中條列出名字與公司，右側提供「查看 ❯」的 Postback 按鈕，點擊後才單獨顯示該張詳細名片。

這樣既保持了版面整潔，又巧妙解決了訊息上限的問題！

```python
        # 1. 檢查是否有待確認的修改操作...
        
        # 2. 如果沒有 pending update，才處理名片顯示
        elif found_card_ids:
            if len(found_card_ids) <= 4:
                # 數量小於等於 4，直接顯示 Carousel 詳細名片卡片
                for card_id in found_card_ids:
                    card_data = firebase_utils.get_card_by_id(user_id, card_id)
                    if card_data:
                        reply_msgs.append(
                            flex_messages.get_namecard_flex_msg(card_data, card_id)
                        )
            else:
                # 數量大於 4，以清單 Flex Message 顯示進行消歧義
                cards_list = []
                for card_id in found_card_ids:
                    card_data = firebase_utils.get_card_by_id(user_id, card_id)
                    if card_data:
                        cards_list.append({
                            "card_id": card_id,
                            "name": card_data.get("name", "N/A"),
                            "company": card_data.get("company", "N/A"),
                            "title": card_data.get("title", "N/A")
                        })
                if cards_list:
                    list_msg = flex_messages.get_namecard_list_flex_msg(
                        cards=cards_list,
                        title_text="🔍 找到多個相符的名片"
                    )
                    reply_msgs.append(list_msg)
```

---

### 踩坑二：AI 誤觸修改的悲劇——二次確認機制

在 ADK 代理人架構下，使用者可以透過「幫我改 Evan 的電話為...」來直接修改資料。但如果大模型在對話中「聽錯了」或是產生「幻覺」，它就會自動調用 `update_namecard_field` 工具，在未經使用者同意的情況下直接改寫 Firebase！

為了人脈資料庫的安全，我們實作了**雙階段確認機制 (Two-Stage Confirmation)**：

1. **延遲寫入**：在 ADK Tool 被調用時，我們只將「待修改內容」暫存至 `user_states` 中，回傳 `True` 騙過 LLM。
2. **傳送確認卡片**：主程式偵測到有 pending 狀態，便會產生一張帶有「確定修改」與「取消」按鈕的 Flex Message。
3. **執行寫入**：使用者點擊「確定修改」後（透過 Postback），系統才真正將資料寫入 Firebase。

這不僅完美防範了 AI 誤觸工具，也讓使用者在修改資料時有了絕對的主控權！

```python
    # handle_postback_event 中處理確認修改
    elif action == 'confirm_update':
        state = user_states.get(user_id, {})
        if state.get('action') == 'pending_update':
            update_type = state.get('update_type')
            card_id = state.get('card_id')
            # 根據 update_type 真正寫入資料庫...
            if success:
                # 回覆修改成功與更新後的 Flex Card
```

---

# 運維血淚踩坑

除了代碼重構，我們在遷移與部署上也撞到了許多不可忽視的巨坑：

### 踩坑一：Uvicorn 啟動時 Event Loop 崩潰
* **問題**：`bot_instance.py` 在被導入時就全域實例化 `aiohttp.ClientSession()`，此時 Event Loop 還沒啟動，導致容器健康檢查超時直接閃退。
* **解決方案**：設計一個 `LazyLineBotApi` 包裝器，將 `ClientSession` 與 `AsyncLineBotApi` 延遲到第一個 Webhook 請求進來時才實例化，解決了 Import Time 的初始化崩潰。

### 踩坑二：GCP 預設的 Region 導致的 Model 404
* **問題**：Cloud Run 部署在台灣 (`asia-east1`)，SDK 自動去該區域尋找 `gemini-3-flash-preview` 模型，但最新模型僅在 `global` 區提供，拋出 404。
* **解決方案**：在 `app/config.py` 入口強制將 `GOOGLE_CLOUD_LOCATION` 覆寫為 `global`。

### 踩坑三：手動部署 Cloud Run 導致環境變數集體蒸發
* **問題**：在本地使用 `gcloud run deploy` 或 MCP 部署工具上傳本地資料夾時，因為未攜帶任何環境變數參數，導致 Cloud Run 上原本運作正常的 LINE Token、Firebase URL 全部被清空覆蓋，重啟時狂噴 `Specify ChannelSecret as environment variable` 錯誤，線上服務瞬間癱瘓。
* **搶救過程**：
  幸好，Cloud Run 擁有優秀的歷史版本 (Revision) 控制！我們可以使用 `gcloud` 指令查看之前的 Revision 組態，還原遺失的設定：
  ```bash
  # 1. 撈取上一個成功運作的 Revision 詳細組態
  gcloud run revisions describe linebot-namecard-python-00096-d89 --project=line-vertex --region=asia-east1
  ```
  這會吐出當時成功的環境變數。隨後我們執行 `services update` 將這些變數重新補回 Service 組態中，服務立刻無縫滿血復活！
  ```bash
  gcloud run services update linebot-namecard-python --project=line-vertex --region=asia-east1 --set-env-vars="ChannelAccessToken=...,ChannelSecret=..."
  ```
  這也提醒了我們：生產環境的變數管理至關重要，不要輕易使用無環境變數宣告的指令去直接覆蓋現有的 Service 設定。

---

# 總結與效益

重構成 **ADK Agent + Tools + 結構化輸出** 之後，專案獲得了顯著的進化：
1. **100% 格式安全性**：透過 API 原生 Schema 強制約束，名片辨識再也不會因為 Markdown 語法或缺少欄位而報錯。
2. **防爆回覆保護**：限制單次 Carousel 數量為 4，且在大於 4 筆時無縫切換為消歧義清單，完美避開了 LINE 限制。
3. **安全的人脈異動**：引進了二次確認機制，將 AI 的修改請求關進二次確認的沙盒，大幅提升資料安全性。
4. **健全的運維災防**：透過 gcloud 歷史組態還原技術，我們有能力在環境變數被誤清空時，於數分鐘內快速重組並修復服務。

完整且經 linter 優化的程式碼已同步推播至 [GitHub](https://github.com/kkdai/linebot-namecard-python)。希望這篇實戰經驗能幫助大家在打造生產級 AI 語意代理人時少走更多彎路！我們下期見！
