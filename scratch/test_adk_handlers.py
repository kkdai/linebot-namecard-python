import os
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Mock standard modules that connect to Firebase on import
import firebase_admin
firebase_admin.initialize_app = MagicMock()

import aiohttp
from linebot import AsyncLineBotApi, WebhookParser
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient

# Mock config before importing line_handlers
with patch('app.config.PROJECT_ID', 'line-vertex'), \
     patch('app.config.LOCATION', 'global'), \
     patch('app.config.CHANNEL_ACCESS_TOKEN', 'mock_token'), \
     patch('app.config.CHANNEL_SECRET', 'mock_secret'), \
     patch('app.config.FIREBASE_URL', 'https://mock.firebaseio.com/'):
     
    from app import line_handlers
    from app import firebase_utils

class TestADKHandlers(unittest.IsolatedAsyncioTestCase):
    @patch('app.line_handlers.line_bot_api')
    @patch('app.firebase_utils.get_all_cards')
    @patch('app.firebase_utils.get_card_by_id')
    async def test_handle_smart_query(self, mock_get_card, mock_get_all, mock_line_api):
        # 1. Mock Firebase functions
        mock_get_all.return_value = {
            "card_123": {
                "name": "王大明",
                "phone": "0912-345-678",
                "company": "谷歌",
                "email": "daming@google.com"
            }
        }
        mock_get_card.return_value = {
            "name": "王大明",
            "phone": "0912-345-678",
            "company": "谷歌",
            "email": "daming@google.com"
        }
        
        # 2. Mock LINE Bot API reply method
        mock_line_api.reply_message = AsyncMock()
        
        # 3. Create simulated event
        mock_event = MagicMock()
        mock_event.reply_token = "reply_token_123"
        
        # 4. Run the query
        print("\nRunning handle_smart_query simulation for '找王大明的名片'...")
        await line_handlers.handle_smart_query(mock_event, "user_abc", "找王大明的名片")
        
        # 5. Check expectations
        self.assertTrue(mock_line_api.reply_message.called)
        args, kwargs = mock_line_api.reply_message.call_args
        
        reply_token = args[0]
        reply_msgs = args[1]
        
        print("\n--- LINE Bot API Reply Call ---")
        print(f"Reply Token: {reply_token}")
        print(f"Reply Messages Count: {len(reply_msgs)}")
        for i, msg in enumerate(reply_msgs):
            print(f"Message {i+1} Type: {type(msg)}")
            if hasattr(msg, 'text'):
                print(f"Message {i+1} Text: {msg.text}")
        print("--------------------------------\n")
        
        self.assertEqual(reply_token, "reply_token_123")
        self.assertGreaterEqual(len(reply_msgs), 1)

if __name__ == '__main__':
    unittest.main()
