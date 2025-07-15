from urllib.parse import parse_qsl
from linebot.models import FlexSendMessage, PostbackEvent
from linebot.models import MessageEvent, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from linebot import AsyncLineBotApi, WebhookParser
from fastapi import Request, FastAPI, HTTPException
import google.generativeai as genai
import os
import sys
from io import BytesIO
import json

import aiohttp
import PIL.Image
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

# =====================
# config.py (集中管理常數與設定)
# =====================
CHANNEL_SECRET = os.getenv("ChannelSecret", None)
CHANNEL_ACCESS_TOKEN = os.getenv("ChannelAccessToken", None)
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
FIREBASE_URL = os.environ.get("FIREBASE_URL")
NAMECARD_PATH = "namecard"

IMGAGE_PROMPT = """
這是一張名片，你是一個名片秘書。請將以下資訊整理成 json 給我。
如果看不出來的，幫我填寫 N/A
只好 json 就好:
name, title, address, email, phone, company.
其中 phone 的內容格式為 #886-0123-456-789,1234. 沒有分機就忽略 ,1234
"""

# =====================
# 初始化區塊
# =====================
if CHANNEL_SECRET is None:
    print("Specify ChannelSecret as environment variable.")
    sys.exit(1)
if CHANNEL_ACCESS_TOKEN is None:
    print("Specify ChannelAccessToken as environment variable.")
    sys.exit(1)
if GEMINI_KEY is None:
    print("Specify GEMINI_API_KEY as environment variable.")
    sys.exit(1)

# Firebase 初始化
cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_URL})
print("Firebase Admin SDK initialized successfully.")

# Gemini 初始化
genai.configure(api_key=GEMINI_KEY)

# FastAPI 與 LINE Bot 初始化
app = FastAPI()
session = aiohttp.ClientSession()
async_http_client = AiohttpAsyncHttpClient(session)
line_bot_api = AsyncLineBotApi(CHANNEL_ACCESS_TOKEN, async_http_client)
parser = WebhookParser(CHANNEL_SECRET)

# 用一個簡單的字典來暫存使用者的狀態
# 注意：此方法在多實例部署下會有問題，正式環境建議改用 Redis 或 Firestore 等外部儲存來管理狀態
user_states = {}


# =====================
# 工具函式區 (Firebase)
# =====================
def get_all_cards(u_id: str) -> dict:
    """取得使用者所有名片資料"""
    try:
        ref = db.reference(f"{NAMECARD_PATH}/{u_id}")
        namecard_data = ref.get()
        return namecard_data or {}
    except Exception as e:
        print(f"Error fetching namecards: {e}")
        return {}


def add_namecard(namecard_obj: dict, u_id: str) -> str:
    """新增名片資料到 Firebase 並回傳 card_id"""
    try:
        ref = db.reference(f"{NAMECARD_PATH}/{u_id}")
        new_card_ref = ref.push(namecard_obj)
        return new_card_ref.key  # 回傳新資料的唯一 ID
    except Exception as e:
        print(f"Error adding namecard: {e}")
        return None


def update_namecard_memo(card_id: str, u_id: str, memo: str) -> bool:
    """更新指定名片的備忘錄"""
    try:
        ref = db.reference(f"{NAMECARD_PATH}/{u_id}/{card_id}")
        ref.update({"memo": memo})
        return True
    except Exception as e:
        print(f"Error updating memo: {e}")
        return False


def remove_redundant_data(u_id: str) -> None:
    """移除重複 email 的名片資料"""
    try:
        ref = db.reference(f"{NAMECARD_PATH}/{u_id}")
        namecard_data = ref.get()
        if namecard_data:
            email_map = {}
            for key, value in namecard_data.items():
                email = value.get("email")
                if email:
                    if email in email_map:
                        ref.child(key).delete()
                    else:
                        email_map[email] = key
    except Exception as e:
        print(f"Error removing redundant data: {e}")


def check_if_card_exists(namecard_obj: dict, u_id: str) -> str:
    """檢查名片是否已存在 (以 email 為主鍵)，若存在則回傳 card_id"""
    try:
        email = namecard_obj.get("email")
        if not email:
            return None
        ref = db.reference(f"{NAMECARD_PATH}/{u_id}")
        namecard_data = ref.get()
        if namecard_data:
            for card_id, value in namecard_data.items():
                if value.get("email") == email:
                    return card_id  # 回傳已存在名片的 ID
        return None
    except Exception as e:
        print(f"Error checking if namecard exists: {e}")
        return None


# =====================
# 工具函式區 (Gemini)
# =====================
def generate_gemini_text_complete(prompt: list) -> object:
    """Gemini 文字生成，強制要求結構化 JSON 輸出"""
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    response = model.generate_content(prompt)
    return response


def generate_json_from_image(img: PIL.Image.Image, prompt: str) -> object:
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    response = model.generate_content([prompt, img], stream=True)
    response.resolve()
    return response


# =====================
# 工具函式區 (JSON 處理)
# =====================
def load_json_string_to_object(json_str: str) -> dict:
    try:
        # 移除前後可能存在的 markdown 標籤
        json_str = json_str.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(json_str)
    except Exception as e:
        print(f"Error loading JSON string: {e}, string was: {json_str}")
        return {}


def parse_gemini_result_to_json(card_json_str: str) -> dict:
    try:
        return json.loads(card_json_str)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return {}


# =====================
# Flex Message 組裝
# =====================
def get_namecard_flex_msg(card_data: dict, card_id: str) -> FlexSendMessage:
    # 確保基本資料存在
    name = card_data.get("name", "N/A")
    title = card_data.get("title", "N/A")
    company = card_data.get("company", "N/A")
    address = card_data.get("address", "N/A")
    phone = card_data.get("phone", "N/A")
    email = card_data.get("email", "N/A")
    memo = card_data.get("memo", "") # 讀取備忘錄

    flex_msg = {
        "type": "bubble",
        "size": "giga",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": company, "color": "#ffffff", "size": "lg"},
                        {"type": "text", "text": name, "color": "#ffffff", "size": "xxl", "weight": "bold"},
                        {"type": "text", "text": title, "color": "#ffffff", "size": "md"},
                    ]
                }
            ],
            "paddingAll": "20px",
            "backgroundColor": "#0367D3",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                    {"type": "text", "text": "Phone", "size": "sm", "color": "#555555", "flex": 1},
                    {"type": "text", "text": phone, "size": "sm", "color": "#111111", "align": "end", "flex": 3}
                ]},
                {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                    {"type": "text", "text": "Email", "size": "sm", "color": "#555555", "flex": 1},
                    {"type": "text", "text": email, "size": "sm", "color": "#111111", "align": "end", "flex": 3}
                ]},
                {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                    {"type": "text", "text": "Address", "size": "sm", "color": "#555555", "flex": 1},
                    {"type": "text", "text": address, "size": "sm", "color": "#111111", "align": "end", "wrap": True, "flex": 3}
                ]},
                {"type": "separator", "margin": "xxl"},
                {"type": "box", "layout": "vertical", "margin": "md", "contents": [
                    {"type": "text", "text": "備忘錄", "size": "md", "color": "#555555"},
                    {"type": "text", "text": memo or "尚無備忘錄", "color": "#111111", "size": "sm", "wrap": True, "margin": "md"}
                ]}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "link",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "新增/修改記事",
                        "data": f"action=add_memo&card_id={card_id}",
                        "displayText": f"我想為 {name} 新增記事"
                    }
                }
            ]
        },
        "styles": {
            "footer": {
                "separator": True,
            }
        },
    }

    return FlexSendMessage(alt_text=f"{name} 的名片", contents=flex_msg)


# =====================
# FastAPI 路由 (主入口)
# =====================
@app.post("/")
async def handle_callback(request: Request):
    signature = request.headers["X-Line-Signature"]
    body = (await request.body()).decode()
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    for event in events:
        user_id = event.source.user_id
        if isinstance(event, MessageEvent):
            if event.message.type == "text":
                await handle_text_event(event, user_id)
            elif event.message.type == "image":
                await handle_image_event(event, user_id)
        elif isinstance(event, PostbackEvent):
            await handle_postback_event(event, user_id)
    return "OK"


# =====================
# 事件處理 (分流)
# =====================
async def handle_postback_event(event: PostbackEvent, user_id: str):
    postback_data = dict(parse_qsl(event.postback.data))
    action = postback_data.get('action')

    if action == 'add_memo':
        card_id = postback_data.get('card_id')
        # 從 Firebase 取得名片主人的名字
        card_ref = db.reference(f"{NAMECARD_PATH}/{user_id}/{card_id}")
        card_doc = card_ref.get()
        if not card_doc:
            await line_bot_api.reply_message(event.reply_token, TextSendMessage(text='找不到該名片資料。'))
            return
        
        card_name = card_doc.get('name', '這位聯絡人')
        # 記錄使用者當前的狀態
        user_states[user_id] = {
            'action': 'adding_memo',
            'card_id': card_id
        }
        # 回覆訊息，引導使用者輸入備忘錄
        reply_text = f"請輸入關於「{card_name}」的備忘錄："
        await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))


async def handle_text_event(event: MessageEvent, user_id: str) -> None:
    msg = event.message.text
    
    # 檢查使用者是否正在新增備忘錄
    if user_id in user_states and user_states[user_id].get('action') == 'adding_memo':
        state = user_states[user_id]
        card_id = state['card_id']
        
        if update_namecard_memo(card_id, user_id, msg):
            await line_bot_api.reply_message(event.reply_token, TextSendMessage(text='備忘錄已成功更新！'))
        else:
            await line_bot_api.reply_message(event.reply_token, TextSendMessage(text='新增備忘錄時發生錯誤，請稍後再試。'))
        
        # 清除使用者狀態
        del user_states[user_id]
        return

    if msg == "test":
        test_namecard = generate_sample_namecard()
        # 測試卡片給一個假的 card_id
        reply_card_msg = get_namecard_flex_msg(test_namecard, "test_card_id")
        await line_bot_api.reply_message(event.reply_token, [reply_card_msg])
    elif msg == "list":
        all_cards = get_all_cards(user_id)
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text=f"總共有 {len(all_cards)} 張名片資料。")],
        )
    elif msg == "remove":
        remove_redundant_data(user_id)
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text="Redundant data removal complete.")],
        )
    else:
        # 智慧查詢名片的邏輯
        all_cards_dict = get_all_cards(user_id)
        if not all_cards_dict:
            await line_bot_api.reply_message(event.reply_token, [TextSendMessage(text="您尚未建立任何名片。")])
            return

        # 將 card_id 加入到每個名片物件中，以便 LLM 能夠回傳
        all_cards_list = []
        for card_id, card_data in all_cards_dict.items():
            card_data_with_id = card_data.copy()
            card_data_with_id['card_id'] = card_id
            all_cards_list.append(card_data_with_id)

        smart_query_prompt = (
            "你是一個名片助理，以下是所有名片資料（JSON 陣列），"
            "請根據使用者輸入的查詢，回傳最相關的一或多張名片 JSON（只回傳 JSON 陣列，不要多餘說明）。"
            "每張名片物件中都要包含 'card_id'.\n"
            f"名片資料: {json.dumps(all_cards_list, ensure_ascii=False)}\n"
            f"查詢: {msg}"
        )
        messages = [{"role": "user", "parts": [smart_query_prompt]}]
        response = generate_gemini_text_complete(messages)

        try:
            card_objs = load_json_string_to_object(response.text)
            if isinstance(card_objs, dict): # 如果只回傳一個物件，也把它轉成 list
                card_objs = [card_objs]

            if not card_objs:
                raise ValueError("Empty result from LLM")

            # 回傳所有可能名片（最多五筆）
            reply_msgs = []
            for card_obj in card_objs[:5]:
                card_id = card_obj.get("card_id")
                if card_id:
                    reply_msgs.append(get_namecard_flex_msg(card_obj, card_id))
            
            if reply_msgs:
                await line_bot_api.reply_message(event.reply_token, reply_msgs)
            else:
                raise ValueError("No card_id found in results")

        except Exception as e:
            print(f"Error processing LLM response: {e}")
            await line_bot_api.reply_message(
                event.reply_token,
                [TextSendMessage(text="查無相關名片資料。")],
            )


async def handle_image_event(event: MessageEvent, user_id: str) -> None:
    message_content = await line_bot_api.get_message_content(event.message.id)
    image_content = b""
    async for s in message_content.iter_content():
        image_content += s
    img = PIL.Image.open(BytesIO(image_content))
    result = generate_json_from_image(img, IMGAGE_PROMPT)
    card_obj = parse_gemini_result_to_json(result.text)
    if not card_obj:
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text=f"無法解析這張名片，請再試一次。 錯誤資訊: {result.text}")]
        )
        return
    
    card_obj = {k.lower(): v for k, v in card_obj.items()}
    
    existing_card_id = check_if_card_exists(card_obj, user_id)
    if existing_card_id:
        # 如果名片已存在，直接取得該名片的完整資料並顯示
        existing_card_data = db.reference(f"{NAMECARD_PATH}/{user_id}/{existing_card_id}").get()
        reply_msg = get_namecard_flex_msg(existing_card_data, existing_card_id)
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text="這個名片已經存在資料庫中。"), reply_msg],
        )
        return

    # 新增名片並取得 card_id
    card_id = add_namecard(card_obj, user_id)
    if card_id:
        reply_msg = get_namecard_flex_msg(card_obj, card_id)
        chinese_reply_msg = TextSendMessage(text="名片資料已經成功加入資料庫。")
        await line_bot_api.reply_message(event.reply_token, [reply_msg, chinese_reply_msg])
    else:
        await line_bot_api.reply_message(event.reply_token, [TextSendMessage(text="儲存名片時發生錯誤。")])


# =====================
# 其他工具函式
# =====================
def generate_sample_namecard() -> dict:
    return {
        "name": "Kevin Dai",
        "title": "Software Engineer",
        "address": "Taipei, Taiwan",
        "email": "aa@bbb.cc",
        "phone": "+886-123-456-789",
        "company": "LINE Taiwan",
        "memo": "This is a test memo."
    }
