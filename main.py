from linebot.models import FlexSendMessage
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

QUERY_PROMPT = """
這是所有的名片資料，請根據輸入文字來查詢相關的名片資料 {all_cards}，
例如: 名字, 職稱, 公司名稱。 查詢問句為： {msg}, 只要回覆我找到的 JSON Data 就好。
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


def add_namecard(namecard_obj: dict, u_id: str) -> None:
    """新增名片資料到 Firebase"""
    try:
        ref = db.reference(f"{NAMECARD_PATH}/{u_id}")
        ref.push(namecard_obj)
    except Exception as e:
        print(f"Error adding namecard: {e}")


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


def check_if_card_exists(namecard_obj: dict, u_id: str) -> bool:
    """檢查名片是否已存在 (以 email 為主鍵)"""
    try:
        email = namecard_obj.get("email")
        if not email:
            return False
        ref = db.reference(f"{NAMECARD_PATH}/{u_id}")
        namecard_data = ref.get()
        if namecard_data:
            for value in namecard_data.values():
                if value.get("email") == email:
                    return True
        return False
    except Exception as e:
        print(f"Error checking if namecard exists: {e}")
        return False


# =====================
# 工具函式區 (Gemini)
# =====================
def generate_gemini_text_complete(prompt: list) -> object:
    """Gemini 文字生成，強制要求結構化 JSON 輸出"""
    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    # 直接要求 Gemini 回傳 JSON 格式
    response = model.generate_content(prompt)
    return response


def generate_json_from_image(img: PIL.Image.Image, prompt: str) -> object:
    model = genai.GenerativeModel(
        "gemini-2.0-flash",
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
        json_str = json_str.replace("'", '"')
        return {k.lower(): v for k, v in json.loads(json_str).items()}
    except Exception as e:
        print(f"Error loading JSON string: {e}")
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
def get_namecard_flex_msg(card_data: dict) -> FlexSendMessage:
    # Using Template

    flex_msg = {
        "type": "bubble",
        "size": "giga",
        "body": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "md",
            "contents": [
                {
                    "type": "image",
                    "aspectMode": "cover",
                    "aspectRatio": "1:1",
                    "flex": 1,
                    "size": "full",
                    "url": "https://raw.githubusercontent.com/kkdai/linebot-smart-namecard/main/img/logo.jpeg",
                },
                {
                    "type": "box",
                    "flex": 4,
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "align": "end",
                            "size": "xxl",
                            "text": f"{card_data.get('name')}",
                            "weight": "bold",
                        },
                        {
                            "type": "text",
                            "align": "end",
                            "size": "sm",
                            "text": f"{card_data.get('title')}",
                        },
                        {
                            "type": "text",
                            "align": "end",
                            "margin": "xxl",
                            "size": "lg",
                            "text": f"{card_data.get('company')}",
                            "weight": "bold",
                        },
                        {
                            "type": "text",
                            "align": "end",
                            "size": "sm",
                            "text": f"{card_data.get('address')}",
                        },
                        {
                            "type": "text",
                            "align": "end",
                            "margin": "xxl",
                            "text": f"{card_data.get('phone')}",
                        },
                        {
                            "type": "text",
                            "align": "end",
                            "text": f"{card_data.get('email')}",
                        },
                        {
                            "type": "text",
                            "align": "end",
                            "text": "更多資訊",
                            "action": {
                                "type": "uri",
                                "uri": "https://github.com/kkdai/linebot-namecard-python",
                            },
                        },
                    ],
                },
            ],
        },
        "styles": {
            "footer": {
                "separator": True,
            }
        },
    }

    print("flex:", flex_msg)
    return FlexSendMessage(alt_text="Namecard", contents=flex_msg)


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
        if not isinstance(event, MessageEvent):
            continue
        user_id = event.source.user_id
        if event.message.type == "text":
            await handle_text_event(event, user_id)
        elif event.message.type == "image":
            await handle_image_event(event, user_id)
    return "OK"


# =====================
# 事件處理 (分流)
# =====================
async def handle_text_event(event: MessageEvent, user_id: str) -> None:
    msg = event.message.text
    if msg == "test":
        test_namecard = generate_sample_namecard()
        reply_card_msg = get_namecard_flex_msg(test_namecard)
        await line_bot_api.reply_message(event.reply_token, [reply_card_msg])
    elif msg == "list":
        all_cards = get_all_cards(user_id)
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text=f"總共有  {len(all_cards)} 張名片資料。")],
        )
    elif msg == "remove":
        remove_redundant_data(user_id)
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text="Redundant data removal complete.")],
        )
    else:
        # 智慧查詢名片的邏輯，將所有名片轉成 list 並用 LLM 查詢
        all_cards_dict = get_all_cards(user_id)
        all_cards_list = list(all_cards_dict.values()) if all_cards_dict else []
        # 若資料量大，可考慮先用關鍵字初步篩選
        # filtered_cards = [c for c in all_cards_list if msg in str(c.values())]
        # 這裡直接全部丟給 LLM
        smart_query_prompt = (
            "你是一個名片助理，以下是所有名片資料（JSON 陣列），"
            "請根據使用者輸入的查詢，回傳最相關的名片 JSON（只回傳 JSON，不要多餘說明）。\n"
            f"名片資料: {json.dumps(all_cards_list, ensure_ascii=False)}\n"
            f"查詢: {msg}"
        )
        # 這裡使用 Gemini 的 text completion API
        messages = [{"role": "user", "parts": smart_query_prompt}]
        response = generate_gemini_text_complete(messages)

        # LLM 回傳可能是陣列或單一物件，需處理
        try:
            print("namecard:", response.text)
            card = load_json_string_to_object(response.text)
            print("card_obj:", card)
            card_objs = json.loads(response.text)
            if isinstance(card_objs, dict):
                card_objs = [card_objs]

            # 回傳所有可能名片（最多五筆）
            if len(card_objs) > 1:
                reply_msg = [
                    get_namecard_flex_msg(card_obj) for card_obj in card_objs[:5]
                ]
                await line_bot_api.reply_message(event.reply_token, reply_msg)
                return

            # 回傳單一名片
            card_obj = card_objs[0]
            reply_msg = get_namecard_flex_msg(card_obj)
            await line_bot_api.reply_message(event.reply_token, [reply_msg])
            return
        except Exception:
            card_objs = []
        if not card_objs:
            await line_bot_api.reply_message(
                event.reply_token,
                [TextSendMessage(text="查無相關名片資料。")],
            )
            return


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
            [
                TextSendMessage(
                    text=f"無法解析這張名片，請再試一次。 錯誤資訊: {result.text}"
                )
            ],
        )
        return
    card_obj = {k.lower(): v for k, v in card_obj.items()}
    if check_if_card_exists(card_obj, user_id):
        reply_msg = get_namecard_flex_msg(card_obj)
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text="這個名片已經存在資料庫中。"), reply_msg],
        )
        return
    add_namecard(card_obj, user_id)
    reply_msg = get_namecard_flex_msg(card_obj)
    chinese_reply_msg = TextSendMessage(text="名片資料已經成功加入資料庫。")
    await line_bot_api.reply_message(event.reply_token, [reply_msg, chinese_reply_msg])


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
    }
