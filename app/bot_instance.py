
import aiohttp
from linebot import AsyncLineBotApi, WebhookParser
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from . import config


class LazyLineBotApi:
    def __init__(self):
        self._api = None
        self.session = None

    def _get_api(self):
        if self._api is None:
            self.session = aiohttp.ClientSession()
            async_http_client = AiohttpAsyncHttpClient(self.session)
            self._api = AsyncLineBotApi(
                config.CHANNEL_ACCESS_TOKEN, async_http_client
            )
        return self._api

    def __getattr__(self, name):
        return getattr(self._get_api(), name)


line_bot_api = LazyLineBotApi()
parser = WebhookParser(config.CHANNEL_SECRET)

user_states = {}


async def close_session():
    if line_bot_api.session:
        await line_bot_api.session.close()
