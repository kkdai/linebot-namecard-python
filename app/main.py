from fastapi import Request, FastAPI, HTTPException
from linebot.models import MessageEvent, PostbackEvent
from linebot.exceptions import InvalidSignatureError
from linebot import WebhookParser
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials
import os
import json

from . import config
from .line_handlers import (
    handle_text_event, handle_image_event, handle_postback_event)
from .bot_instance import line_bot_api, close_session, parser

# =====================
# 初始化區塊
# =====================

# Firebase 初始化
try:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {"databaseURL": config.FIREBASE_URL})
    print("Firebase Admin SDK initialized successfully.")
except Exception as e:
    # 在 Heroku 上，GOOGLE_APPLICATION_CREDENTIALS 可能不是一個有效的檔案路徑
    # 此時需要從環境變數解析 JSON
    gac_str = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if gac_str:
        cred_json = json.loads(gac_str)
        cred = credentials.Certificate(cred_json)
        firebase_admin.initialize_app(
            cred, {"databaseURL": config.FIREBASE_URL})
        print("Firebase Admin SDK initialized successfully from ENV VAR.")
    else:
        print(f"Firebase initialization failed: {e}")
        # 可以選擇在這裡 sys.exit(1) 或讓程式繼續，但 Firebase 功能會失效


# Gemini 初始化
genai.configure(api_key=config.GEMINI_KEY)

# FastAPI 初始化
app = FastAPI()


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


@app.get("/")
async def health_check():
    return {"status": "ok"}


@app.on_event("shutdown")
async def on_shutdown():
    await close_session()
    print("aiohttp session closed.")

