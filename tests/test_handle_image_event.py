import json
import time
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import PIL.Image

from app import line_handlers


def _make_jpeg_bytes(color):
    img = PIL.Image.new("RGB", (10, 10), color=color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


FRONT_BYTES = _make_jpeg_bytes("white")
BACK_BYTES = _make_jpeg_bytes("black")

CARD_JSON = json.dumps({
    "name": "王大明",
    "title": "工程師",
    "company": "測試公司",
    "address": "台北市",
    "phone": "#886-02-1234-5678",
    "email": "david@example.com"
})

MERGED_CARD_JSON = json.dumps({
    "name": "王大明 David Wang",
    "title": "工程師",
    "company": "測試公司",
    "address": "台北市",
    "phone": "#886-02-1234-5678",
    "email": "david@example.com"
})


class FakeMessageContent:
    def __init__(self, content: bytes):
        self._content = content

    async def iter_content(self):
        yield self._content


class FakeMessage:
    def __init__(self, message_id="msg-1"):
        self.id = message_id


class FakeEvent:
    def __init__(self, reply_token="reply-token-1"):
        self.message = FakeMessage()
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
async def test_fresh_image_asks_about_backside_and_does_not_save(
        mock_line_api):
    mock_line_api.get_message_content.return_value = FakeMessageContent(
        FRONT_BYTES)
    fake_response = MagicMock(text=CARD_JSON)

    with patch.object(
        line_handlers.gemini_utils, "generate_json_from_image",
        return_value=fake_response
    ) as mock_single, patch.object(
        line_handlers.firebase_utils, "add_namecard"
    ) as mock_add:
        await line_handlers.handle_image_event(FakeEvent(), "user-1")

        mock_single.assert_called_once()
        mock_add.assert_not_called()

    state = line_handlers.user_states["user-1"]
    assert state["action"] == "pending_backside_confirm"
    assert state["card_obj"]["name"] == "王大明"
    assert state["front_image_bytes"] == FRONT_BYTES

    reply_args = mock_line_api.reply_message.call_args.args
    assert "還有背面嗎" in reply_args[1].text


@pytest.mark.asyncio
async def test_awaiting_backside_image_merges_and_saves(mock_line_api):
    line_handlers.user_states["user-1"] = {
        "action": "awaiting_backside_image",
        "front_image_bytes": FRONT_BYTES,
        "expires_at": time.time() + 300,
    }
    mock_line_api.get_message_content.return_value = FakeMessageContent(
        BACK_BYTES)
    fake_response = MagicMock(text=MERGED_CARD_JSON)

    with patch.object(
        line_handlers.gemini_utils, "generate_json_from_two_images",
        return_value=fake_response
    ) as mock_merge, patch.object(
        line_handlers.gemini_utils, "generate_json_from_image"
    ) as mock_single, patch.object(
        line_handlers.firebase_utils, "check_if_card_exists",
        return_value=None
    ), patch.object(
        line_handlers.firebase_utils, "add_namecard",
        return_value="card-123"
    ) as mock_add:
        await line_handlers.handle_image_event(FakeEvent(), "user-1")

        mock_merge.assert_called_once()
        mock_single.assert_not_called()
        mock_add.assert_called_once()
        saved_card_obj = mock_add.call_args.args[0]
        assert saved_card_obj["name"] == "王大明 David Wang"

    assert "user-1" not in line_handlers.user_states


@pytest.mark.asyncio
async def test_expired_awaiting_backside_treated_as_new_card(
        mock_line_api):
    line_handlers.user_states["user-1"] = {
        "action": "awaiting_backside_image",
        "front_image_bytes": FRONT_BYTES,
        "expires_at": time.time() - 10,
    }
    mock_line_api.get_message_content.return_value = FakeMessageContent(
        BACK_BYTES)
    fake_response = MagicMock(text=CARD_JSON)

    with patch.object(
        line_handlers.gemini_utils, "generate_json_from_image",
        return_value=fake_response
    ) as mock_single, patch.object(
        line_handlers.gemini_utils, "generate_json_from_two_images"
    ) as mock_merge, patch.object(
        line_handlers.firebase_utils, "add_namecard"
    ) as mock_add:
        await line_handlers.handle_image_event(FakeEvent(), "user-1")

        mock_single.assert_called_once()
        mock_merge.assert_not_called()
        mock_add.assert_not_called()

    state = line_handlers.user_states["user-1"]
    assert state["action"] == "pending_backside_confirm"


@pytest.mark.asyncio
async def test_merge_parse_failure_clears_state_and_replies_error(
        mock_line_api):
    line_handlers.user_states["user-1"] = {
        "action": "awaiting_backside_image",
        "front_image_bytes": FRONT_BYTES,
        "expires_at": time.time() + 300,
    }
    mock_line_api.get_message_content.return_value = FakeMessageContent(
        BACK_BYTES)
    fake_response = MagicMock(text="not valid json")

    with patch.object(
        line_handlers.gemini_utils, "generate_json_from_two_images",
        return_value=fake_response
    ):
        await line_handlers.handle_image_event(FakeEvent(), "user-1")

    assert "user-1" not in line_handlers.user_states
    reply_args = mock_line_api.reply_message.call_args.args
    assert "無法解析" in reply_args[1][0].text
