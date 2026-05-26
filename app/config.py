import os
import sys

# Force GOOGLE_CLOUD_LOCATION to global so that Vertex AI and ADK look
# for models in the global region
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

# =====================
# LINE Bot 設定
# =====================
CHANNEL_SECRET = os.getenv("ChannelSecret", None)
CHANNEL_ACCESS_TOKEN = os.getenv("ChannelAccessToken", None)

# =====================
# API 金鑰設定
# =====================
PROJECT_ID = os.getenv("PROJECT_ID", None)
LOCATION = os.getenv("LOCATION", "global")

# =====================
# Firebase 設定
# =====================
FIREBASE_URL = os.environ.get("FIREBASE_URL")
FIREBASE_STORAGE_BUCKET = os.environ.get("FIREBASE_STORAGE_BUCKET")
NAMECARD_PATH = "namecard"

# =====================
# Gemini Prompt 設定
# =====================
IMGAGE_PROMPT = """
這是一張名片，你是一個名片秘書。請將以下資訊整理成 json 給我。
如果看不出來的，幫我填寫 N/A
只好 json 就好:
name, title, address, email, phone, company.
其中 phone 的內容格式為 #886-0123-456-789,1234. 沒有分機就忽略 ,1234
"""

# =====================
# 環境變數檢查
# =====================
if CHANNEL_SECRET is None:
    print("Specify ChannelSecret as environment variable.")
    sys.exit(1)
if CHANNEL_ACCESS_TOKEN is None:
    print("Specify ChannelAccessToken as environment variable.")
    sys.exit(1)
if PROJECT_ID is None:
    print("Specify PROJECT_ID as environment variable.")
    sys.exit(1)
if FIREBASE_URL is None:
    print("Specify FIREBASE_URL as environment variable.")
    sys.exit(1)
