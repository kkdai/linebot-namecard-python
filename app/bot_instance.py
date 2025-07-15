
import aiohttp
from linebot import AsyncLineBotApi
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from . import config

session = aiohttp.ClientSession()
async_http_client = AiohttpAsyncHttpClient(session)
line_bot_api = AsyncLineBotApi(config.CHANNEL_ACCESS_TOKEN, async_http_client)

user_states = {}

async def close_session():
    await session.close()
