from unittest.mock import AsyncMock, patch

import pytest

from app import line_handlers


class FakeMessage:
    def __init__(self, text):
        self.text = text


class FakeTextEvent:
    def __init__(self, text, reply_token="reply-token-1"):
        self.message = FakeMessage(text)
        self.reply_token = reply_token


@pytest.fixture(autouse=True)
def clear_user_states():
    line_handlers.user_states.clear()
    yield
    line_handlers.user_states.clear()


@pytest.mark.asyncio
async def test_text_during_pending_backside_confirm_clears_state():
    line_handlers.user_states["user-1"] = {
        "action": "pending_backside_confirm",
        "card_obj": {},
        "front_image_bytes": b"x",
        "expires_at": 9999999999,
    }
    event = FakeTextEvent("幫我查一下王大明")

    with patch.object(
        line_handlers, "handle_smart_query", new=AsyncMock()
    ) as mock_query:
        await line_handlers.handle_text_event(event, "user-1")

        mock_query.assert_awaited_once_with(
            event, "user-1", "幫我查一下王大明")

    assert "user-1" not in line_handlers.user_states


@pytest.mark.asyncio
async def test_text_during_awaiting_backside_image_clears_state():
    line_handlers.user_states["user-1"] = {
        "action": "awaiting_backside_image",
        "front_image_bytes": b"x",
        "expires_at": 9999999999,
    }
    event = FakeTextEvent("查詢")

    with patch.object(
        line_handlers, "handle_smart_query", new=AsyncMock()
    ) as mock_query:
        await line_handlers.handle_text_event(event, "user-1")

        mock_query.assert_awaited_once()

    assert "user-1" not in line_handlers.user_states


@pytest.mark.asyncio
async def test_remove_command_without_pending_state_still_works():
    event = FakeTextEvent("remove")

    with patch.object(
        line_handlers.firebase_utils, "remove_redundant_data"
    ) as mock_remove, patch.object(
        line_handlers, "line_bot_api", new=AsyncMock()
    ) as mock_api:
        await line_handlers.handle_text_event(event, "user-1")

        mock_remove.assert_called_once_with("user-1")
        mock_api.reply_message.assert_awaited_once()
