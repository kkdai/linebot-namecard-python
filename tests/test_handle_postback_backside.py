import time
from unittest.mock import AsyncMock, patch

import pytest

from app import line_handlers

CARD_OBJ = {
    "name": "王大明",
    "title": "工程師",
    "company": "測試公司",
    "address": "台北市",
    "phone": "#886-02-1234-5678",
    "email": "david@example.com"
}


class FakePostback:
    def __init__(self, data):
        self.data = data


class FakePostbackEvent:
    def __init__(self, data, reply_token="reply-token-1"):
        self.postback = FakePostback(data)
        self.reply_token = reply_token


@pytest.fixture(autouse=True)
def clear_user_states():
    line_handlers.user_states.clear()
    yield
    line_handlers.user_states.clear()


@pytest.fixture
def mock_line_api():
    with patch.object(
        line_handlers, "line_bot_api", new=AsyncMock()
    ) as mock_api:
        yield mock_api


@pytest.mark.asyncio
async def test_backside_confirm_yes_sets_awaiting_state(mock_line_api):
    line_handlers.user_states["user-1"] = {
        "action": "pending_backside_confirm",
        "card_obj": CARD_OBJ,
        "front_image_bytes": b"front-bytes",
        "expires_at": time.time() + 300,
    }
    event = FakePostbackEvent(
        "action=backside_confirm&has_backside=yes")

    await line_handlers.handle_postback_event(event, "user-1")

    state = line_handlers.user_states["user-1"]
    assert state["action"] == "awaiting_backside_image"
    assert state["front_image_bytes"] == b"front-bytes"
    reply_args = mock_line_api.reply_message.call_args.args
    assert "背面照片" in reply_args[1].text


@pytest.mark.asyncio
async def test_backside_confirm_no_finalizes_card(mock_line_api):
    line_handlers.user_states["user-1"] = {
        "action": "pending_backside_confirm",
        "card_obj": CARD_OBJ,
        "front_image_bytes": b"front-bytes",
        "expires_at": time.time() + 300,
    }
    event = FakePostbackEvent(
        "action=backside_confirm&has_backside=no")

    with patch.object(
        line_handlers, "_finalize_and_save_card", new=AsyncMock()
    ) as mock_finalize:
        await line_handlers.handle_postback_event(event, "user-1")

        mock_finalize.assert_awaited_once_with(CARD_OBJ, event, "user-1")

    assert "user-1" not in line_handlers.user_states


@pytest.mark.asyncio
async def test_backside_confirm_without_pending_state_replies_expired(
        mock_line_api):
    event = FakePostbackEvent(
        "action=backside_confirm&has_backside=yes")

    await line_handlers.handle_postback_event(event, "user-1")

    reply_args = mock_line_api.reply_message.call_args.args
    assert "過期" in reply_args[1].text


@pytest.mark.asyncio
async def test_backside_confirm_expired_state_replies_expired(
        mock_line_api):
    line_handlers.user_states["user-1"] = {
        "action": "pending_backside_confirm",
        "card_obj": CARD_OBJ,
        "front_image_bytes": b"front-bytes",
        "expires_at": time.time() - 10,
    }
    event = FakePostbackEvent(
        "action=backside_confirm&has_backside=yes")

    await line_handlers.handle_postback_event(event, "user-1")

    assert "user-1" not in line_handlers.user_states
    reply_args = mock_line_api.reply_message.call_args.args
    assert "過期" in reply_args[1].text


@pytest.mark.asyncio
async def test_backside_confirm_stale_does_not_clear_unrelated_state(
        mock_line_api):
    line_handlers.user_states["user-1"] = {
        "action": "editing_field",
        "card_id": "x",
        "field": "phone",
    }
    event = FakePostbackEvent(
        "action=backside_confirm&has_backside=yes")

    await line_handlers.handle_postback_event(event, "user-1")

    assert line_handlers.user_states["user-1"] == {
        "action": "editing_field",
        "card_id": "x",
        "field": "phone",
    }
    reply_args = mock_line_api.reply_message.call_args.args
    assert "過期" in reply_args[1].text
