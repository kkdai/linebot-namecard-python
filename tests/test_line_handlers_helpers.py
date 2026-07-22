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


class FakeEvent:
    def __init__(self, reply_token="reply-token-1"):
        self.reply_token = reply_token


@pytest.fixture(autouse=True)
def clear_user_states():
    line_handlers.user_states.clear()
    yield
    line_handlers.user_states.clear()


def test_sweep_expired_states_removes_only_expired_entries():
    line_handlers.user_states["expired-user"] = {
        "action": "awaiting_backside_image",
        "front_image_bytes": b"front-bytes",
        "expires_at": time.time() - 10,
    }
    line_handlers.user_states["active-user"] = {
        "action": "pending_backside_confirm",
        "card_obj": CARD_OBJ,
        "front_image_bytes": b"front-bytes",
        "expires_at": time.time() + 300,
    }
    line_handlers.user_states["memo-user"] = {
        "action": "adding_memo",
        "card_id": "card-1",
    }

    line_handlers.sweep_expired_states()

    assert "expired-user" not in line_handlers.user_states
    assert "active-user" in line_handlers.user_states
    assert "memo-user" in line_handlers.user_states


def test_get_backside_confirm_quick_reply_has_two_postback_buttons():
    quick_reply = line_handlers.get_backside_confirm_quick_reply()
    datas = [item.action.data for item in quick_reply.items]
    assert "action=backside_confirm&has_backside=yes" in datas
    assert "action=backside_confirm&has_backside=no" in datas


@pytest.mark.asyncio
async def test_finalize_and_save_card_saves_new_card():
    event = FakeEvent()
    with patch.object(
        line_handlers.firebase_utils, "check_if_card_exists",
        return_value=None
    ), patch.object(
        line_handlers.firebase_utils, "add_namecard",
        return_value="new-card-id"
    ), patch.object(
        line_handlers, "line_bot_api", new=AsyncMock()
    ) as mock_api:
        await line_handlers._finalize_and_save_card(
            CARD_OBJ, event, "user-1")

        mock_api.reply_message.assert_awaited_once()
        args = mock_api.reply_message.call_args.args
        assert args[0] == "reply-token-1"
        texts = [msg.text for msg in args[1] if hasattr(msg, "text")]
        assert any("成功加入資料庫" in t for t in texts)


@pytest.mark.asyncio
async def test_finalize_and_save_card_detects_duplicate():
    event = FakeEvent()
    with patch.object(
        line_handlers.firebase_utils, "check_if_card_exists",
        return_value="existing-id"
    ), patch.object(
        line_handlers.firebase_utils, "get_card_by_id",
        return_value=CARD_OBJ
    ), patch.object(
        line_handlers.firebase_utils, "add_namecard"
    ) as mock_add, patch.object(
        line_handlers, "line_bot_api", new=AsyncMock()
    ) as mock_api:
        await line_handlers._finalize_and_save_card(
            CARD_OBJ, event, "user-1")

        mock_add.assert_not_called()
        args = mock_api.reply_message.call_args.args
        texts = [msg.text for msg in args[1] if hasattr(msg, "text")]
        assert any("已經存在" in t for t in texts)
