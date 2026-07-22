# 名片正反面辨識合併 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓使用者依序傳送名片正面、背面圖片後，系統詢問「還有背面嗎」並在確認後將兩張圖片一次送給 Gemini 合併辨識成單一筆名片資料，維持既有重複檢查與存檔流程不變。

**Architecture:** 在既有的 `user_states` 記憶體狀態機（`app/line_handlers.py`）中新增兩個暫存狀態（`pending_backside_confirm` / `awaiting_backside_image`，皆帶 5 分鐘逾時），並新增 `gemini_utils.generate_json_from_two_images` 讓 Gemini 在同一次呼叫中看到正反兩張圖片後直接輸出合併後的結構化 JSON。既有的重複檢查＋存檔邏輯抽成共用函式 `_finalize_and_save_card`，讓單面／雙面兩條路徑最終收斂到同一段程式碼。

**Tech Stack:** Python 3.10、FastAPI、Vertex AI (`vertexai.generative_models`)、LINE Messaging API SDK (`linebot`)、Pillow、pytest + pytest-asyncio（新增的測試工具）。

## Global Constraints

- 對外文字一律使用繁體中文，語氣比照現有訊息（例如「請稍後再試」「已成功加入資料庫」）。
- Lint 規則：`flake8`，每行最長 79 字元（沿用專案既有風格）。
- 不新增任何正式執行期相依套件；測試專用套件（`pytest`、`pytest-asyncio`）放進新的 `requirements-dev.txt`，不動 `requirements.txt`。
- 狀態機沿用既有 `user_states[user_id] = {...}` 記憶體字典模式與 `PostbackAction(data="action=...&...")` + `parse_qsl` 的既有寫法，不引入新的儲存機制或框架。
- 所有測試必須用 mock 隔離 Vertex AI（Gemini）與 Firebase 的真實網路呼叫；測試套件執行時不需要真實 GCP 憑證或網路連線（僅需假的環境變數讓 `app.config` 的必填檢查通過）。
- Commit 訊息不加 `Co-Authored-By` 或任何 AI 掛名字樣，一律以現有 git 身分提交（`git commit -m "..."`，不使用 heredoc 附加署名）。
- 重複檢查（`firebase_utils.check_if_card_exists`）只能發生在「最終資料底定之後」（單面選擇無背面，或雙面合併完成後），不可在正面辨識剛完成時就提前判斷。

---

## 背景：測試基礎設施現況

專案目前沒有 `tests/` 目錄或 pytest 設定；唯一既有的「測試」是 `scratch/test_gemini_schema.py`，會打真實 Vertex AI API。本計畫會新增一個標準的 `tests/` 目錄與 `conftest.py`。

重要限制：`app/config.py` 在 import 時就會檢查 `ChannelSecret`、`ChannelAccessToken`、`PROJECT_ID`、`FIREBASE_URL` 四個環境變數，沒設定就會 `sys.exit(1)`。因此任何測試在 import `app.*` 之前，必須先用假值設定好這四個環境變數（`conftest.py` 負責）。已驗證：`vertexai.init(project="test-project", location="global")` 在沒有真實憑證的情況下可以正常執行不噴錯（只是在本地設定 SDK 設定值，不會打網路），因此匯入 `app.gemini_utils`（會在 import 時呼叫 `vertexai.init`）在測試環境中是安全的。

---

### Task 1: 建立 pytest 測試基礎設施

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/conftest.py`
- Create: `tests/test_setup_sanity.py`

**Interfaces:**
- Consumes: `app.config.PROJECT_ID`（既有模組屬性，用來驗證假環境變數確實生效）
- Produces: 之後所有任務的測試檔都依賴 `tests/conftest.py` 在 import `app.*` 之前設定好假環境變數這件事。

- [ ] **Step 1: 建立 `requirements-dev.txt`**

```
pytest==9.0.2
pytest-asyncio==1.3.0
```

- [ ] **Step 2: 安裝測試相依套件**

Run: `pip install -r requirements-dev.txt`
Expected: 安裝成功（本機環境已裝有相同版本，應直接顯示 `Requirement already satisfied`）。

- [ ] **Step 3: 寫會失敗的 sanity test**

建立 `tests/test_setup_sanity.py`：

```python
from app import config


def test_project_id_is_test_value():
    assert config.PROJECT_ID == "test-project"
```

- [ ] **Step 4: 執行測試，確認失敗**

Run: `pytest tests/test_setup_sanity.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app'`，或 `app.config` 因為缺環境變數而在 import 時 `SystemExit`）——因為 `tests/conftest.py` 還不存在。

- [ ] **Step 5: 建立 `tests/conftest.py`**

```python
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

os.environ.setdefault("ChannelSecret", "test-channel-secret")
os.environ.setdefault("ChannelAccessToken", "test-channel-access-token")
os.environ.setdefault("PROJECT_ID", "test-project")
os.environ.setdefault(
    "FIREBASE_URL", "https://test-project.firebaseio.com/"
)
```

- [ ] **Step 6: 再次執行測試，確認通過**

Run: `pytest tests/test_setup_sanity.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add requirements-dev.txt tests/conftest.py tests/test_setup_sanity.py
git commit -m "test: add pytest infrastructure for app test suite"
```

---

### Task 2: `gemini_utils.generate_json_from_two_images`（正反面合併辨識）

**Files:**
- Modify: `app/config.py`（在 `IMGAGE_PROMPT` 後新增 `DOUBLE_SIDED_IMAGE_PROMPT`）
- Modify: `app/gemini_utils.py`（新增 `generate_json_from_two_images`）
- Test: `tests/test_gemini_utils_two_images.py`

**Interfaces:**
- Consumes: `app.gemini_utils.NAMECARD_SCHEMA`（既有 dict）、`app.gemini_utils.pil_to_bytes`（既有函式）
- Produces: `generate_json_from_two_images(front_img: PIL.Image.Image, back_img: PIL.Image.Image, prompt: str) -> object`，回傳值 `.text` 為 JSON 字串（與 `generate_json_from_image` 回傳型別一致）。`config.DOUBLE_SIDED_IMAGE_PROMPT: str` 供 Task 4 呼叫時使用。

- [ ] **Step 1: 寫失敗的測試**

建立 `tests/test_gemini_utils_two_images.py`：

```python
import json
from unittest.mock import MagicMock, patch

import PIL.Image

from app import gemini_utils, config


def _make_test_image(color):
    return PIL.Image.new("RGB", (10, 10), color=color)


def test_generate_json_from_two_images_sends_both_images_in_one_call():
    front_img = _make_test_image("white")
    back_img = _make_test_image("black")
    fake_response = MagicMock()
    fake_response.text = json.dumps({
        "name": "王大明 David Wang",
        "title": "工程師",
        "company": "科技公司",
        "address": "台北市",
        "phone": "#886-02-1234-5678",
        "email": "david@example.com"
    })

    with patch.object(gemini_utils, "GenerativeModel") as mock_model_cls:
        mock_model = mock_model_cls.return_value
        mock_model.generate_content.return_value = fake_response

        result = gemini_utils.generate_json_from_two_images(
            front_img, back_img, config.DOUBLE_SIDED_IMAGE_PROMPT
        )

        assert result is fake_response
        mock_model_cls.assert_called_once_with(
            "gemini-3-flash-preview",
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": gemini_utils.NAMECARD_SCHEMA
            },
        )
        call_args = mock_model.generate_content.call_args
        contents = call_args.args[0]
        assert contents[0] == config.DOUBLE_SIDED_IMAGE_PROMPT
        assert len(contents) == 3
        assert call_args.kwargs["stream"] is False
        assert call_args.kwargs["labels"] == {"client_id": "namecard"}
```

- [ ] **Step 2: 執行測試，確認失敗**

Run: `pytest tests/test_gemini_utils_two_images.py -v`
Expected: FAIL（`AttributeError: module 'app.config' has no attribute 'DOUBLE_SIDED_IMAGE_PROMPT'` 或 `AttributeError: module 'app.gemini_utils' has no attribute 'generate_json_from_two_images'`）。

- [ ] **Step 3: 修改 `app/config.py`**

找到這段（`IMGAGE_PROMPT` 定義後緊接環境變數檢查註解）：

```python
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
```

改成：

```python
IMGAGE_PROMPT = """
這是一張名片，你是一個名片秘書。請將以下資訊整理成 json 給我。
如果看不出來的，幫我填寫 N/A
只好 json 就好:
name, title, address, email, phone, company.
其中 phone 的內容格式為 #886-0123-456-789,1234. 沒有分機就忽略 ,1234
"""

DOUBLE_SIDED_IMAGE_PROMPT = IMGAGE_PROMPT + """
這兩張圖片是同一張名片的正面與背面，請整合成一筆完整資料。
若同一欄位中英文都有出現（如姓名、公司），請合併呈現
（例如「王大明 David Wang」）；
若某欄位只有一面出現，直接採用該面的值；忽略明顯重複的資訊。
"""

# =====================
# 環境變數檢查
# =====================
```

- [ ] **Step 4: 修改 `app/gemini_utils.py`**

找到檔案結尾這段（`generate_json_from_image` 的最後幾行）：

```python
    img_part = Part.from_data(data=pil_to_bytes(img), mime_type="image/jpeg")
    response = model.generate_content(
        [prompt, img_part],
        stream=False,
        labels={"client_id": "namecard"}
    )
    return response
```

改成（保留原本內容，並在檔案最後新增函式）：

```python
    img_part = Part.from_data(data=pil_to_bytes(img), mime_type="image/jpeg")
    response = model.generate_content(
        [prompt, img_part],
        stream=False,
        labels={"client_id": "namecard"}
    )
    return response


def generate_json_from_two_images(
        front_img: PIL.Image.Image,
        back_img: PIL.Image.Image,
        prompt: str) -> object:
    model = GenerativeModel(
        "gemini-3-flash-preview",
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": NAMECARD_SCHEMA
        },
    )
    front_part = Part.from_data(
        data=pil_to_bytes(front_img), mime_type="image/jpeg")
    back_part = Part.from_data(
        data=pil_to_bytes(back_img), mime_type="image/jpeg")
    response = model.generate_content(
        [prompt, front_part, back_part],
        stream=False,
        labels={"client_id": "namecard"}
    )
    return response
```

- [ ] **Step 5: 執行測試，確認通過**

Run: `pytest tests/test_gemini_utils_two_images.py -v`
Expected: PASS

- [ ] **Step 6: Lint 檢查**

Run: `flake8 app/config.py app/gemini_utils.py`
Expected: 無輸出（無違規）

- [ ] **Step 7: Commit**

```bash
git add app/config.py app/gemini_utils.py tests/test_gemini_utils_two_images.py
git commit -m "feat: add double-sided namecard merge via Gemini"
```

---

### Task 3: 共用函式 `_finalize_and_save_card` 與背面確認 Quick Reply

**Files:**
- Modify: `app/line_handlers.py`
- Test: `tests/test_line_handlers_helpers.py`

**Interfaces:**
- Consumes: `firebase_utils.check_if_card_exists`, `firebase_utils.get_card_by_id`, `firebase_utils.add_namecard`, `flex_messages.get_namecard_flex_msg`, `get_quick_reply_items()`（皆為既有函式，簽名不變）
- Produces:
  - `async def _finalize_and_save_card(card_obj: dict, event: MessageEvent | PostbackEvent, user_id: str) -> None`（Task 4、5 會呼叫）
  - `def get_backside_confirm_quick_reply() -> QuickReply`（Task 4 會呼叫），內含兩顆 `PostbackAction`，`data` 分別為 `"action=backside_confirm&has_backside=yes"` 與 `"action=backside_confirm&has_backside=no"`
  - `PENDING_BACKSIDE_TIMEOUT_SECONDS = 300`（模組層級常數，Task 4、5 皆會用到）

- [ ] **Step 1: 寫失敗的測試**

建立 `tests/test_line_handlers_helpers.py`：

```python
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
```

- [ ] **Step 2: 執行測試，確認失敗**

Run: `pytest tests/test_line_handlers_helpers.py -v`
Expected: FAIL（`AttributeError: module 'app.line_handlers' has no attribute 'get_backside_confirm_quick_reply'` / `'_finalize_and_save_card'`）。

- [ ] **Step 3: 新增 `import time` 與逾時常數**

找到檔案最上方的 import 區塊：

```python
from urllib.parse import parse_qsl
from linebot.models import (
    PostbackEvent, MessageEvent, TextSendMessage, ImageSendMessage,
    QuickReply, QuickReplyButton, PostbackAction
)
```

改成：

```python
import time
from urllib.parse import parse_qsl
from linebot.models import (
    PostbackEvent, MessageEvent, TextSendMessage, ImageSendMessage,
    QuickReply, QuickReplyButton, PostbackAction
)
```

找到：

```python
FIELD_LABELS = {
    "name": "姓名", "title": "職稱", "company": "公司",
    "address": "地址", "phone": "電話", "email": "Email"
}
```

改成：

```python
FIELD_LABELS = {
    "name": "姓名", "title": "職稱", "company": "公司",
    "address": "地址", "phone": "電話", "email": "Email"
}

PENDING_BACKSIDE_TIMEOUT_SECONDS = 300
```

- [ ] **Step 4: 新增 `get_backside_confirm_quick_reply`**

找到 `get_quick_reply_items` 函式結尾與下一個函式定義之間的這段：

```python
        QuickReplyButton(
            action=PostbackAction(
                label="ℹ️ 說明",
                data="action=show_help"
            )
        )
    ])


async def handle_postback_event(event: PostbackEvent, user_id: str):
```

改成：

```python
        QuickReplyButton(
            action=PostbackAction(
                label="ℹ️ 說明",
                data="action=show_help"
            )
        )
    ])


def get_backside_confirm_quick_reply():
    """建立「這張名片還有背面嗎」的 Quick Reply 按鈕"""
    return QuickReply(items=[
        QuickReplyButton(
            action=PostbackAction(
                label="有背面",
                data="action=backside_confirm&has_backside=yes"
            )
        ),
        QuickReplyButton(
            action=PostbackAction(
                label="沒有，直接儲存",
                data="action=backside_confirm&has_backside=no"
            )
        )
    ])


async def handle_postback_event(event: PostbackEvent, user_id: str):
```

- [ ] **Step 5: 新增 `_finalize_and_save_card`**

找到（`handle_image_event` 定義前）：

```python
async def handle_image_event(event: MessageEvent, user_id: str) -> None:
    message_content = await line_bot_api.get_message_content(event.message.id)
```

改成：

```python
async def _finalize_and_save_card(
        card_obj: dict,
        event: MessageEvent | PostbackEvent,
        user_id: str) -> None:
    """執行重複檢查、存檔並回覆使用者（單面與正反面合併後共用）"""
    existing_card_id = firebase_utils.check_if_card_exists(card_obj, user_id)
    if existing_card_id:
        existing_card_data = firebase_utils.get_card_by_id(
            user_id, existing_card_id)
        reply_msg = flex_messages.get_namecard_flex_msg(
            existing_card_data, existing_card_id)
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(
                text="這個名片已經存在資料庫中。",
                quick_reply=get_quick_reply_items()
            ), reply_msg],
        )
        return

    card_id = firebase_utils.add_namecard(card_obj, user_id)
    if card_id:
        reply_msg = flex_messages.get_namecard_flex_msg(card_obj, card_id)
        chinese_reply_msg = TextSendMessage(
            text="名片資料已經成功加入資料庫。",
            quick_reply=get_quick_reply_items()
        )
        await line_bot_api.reply_message(
            event.reply_token, [reply_msg, chinese_reply_msg])
    else:
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(
                text="儲存名片時發生錯誤。",
                quick_reply=get_quick_reply_items()
            )])


async def handle_image_event(event: MessageEvent, user_id: str) -> None:
    message_content = await line_bot_api.get_message_content(event.message.id)
```

- [ ] **Step 6: 執行測試，確認通過**

Run: `pytest tests/test_line_handlers_helpers.py -v`
Expected: PASS

- [ ] **Step 7: Lint 檢查**

Run: `flake8 app/line_handlers.py`
Expected: 無輸出

- [ ] **Step 8: Commit**

```bash
git add app/line_handlers.py tests/test_line_handlers_helpers.py
git commit -m "refactor: extract shared card finalize helper and backside quick reply"
```

---

### Task 4: `handle_image_event` — 詢問背面與合併辨識流程

**Files:**
- Modify: `app/line_handlers.py`
- Test: `tests/test_handle_image_event.py`

**Interfaces:**
- Consumes: `gemini_utils.generate_json_from_image`, `gemini_utils.generate_json_from_two_images`（Task 2）, `_finalize_and_save_card`、`get_backside_confirm_quick_reply`、`PENDING_BACKSIDE_TIMEOUT_SECONDS`（Task 3）, `utils.parse_gemini_result_to_json`（既有）
- Produces: `handle_image_event` 新行為——正面辨識完先問背面（設定 `user_states[user_id]['action'] = 'pending_backside_confirm'`），確認有背面後在下一張圖片時走合併路徑（`'action' == 'awaiting_backside_image'`），逾時則視為全新名片。

- [ ] **Step 1: 寫失敗的測試**

建立 `tests/test_handle_image_event.py`：

```python
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
```

- [ ] **Step 2: 執行測試，確認失敗**

Run: `pytest tests/test_handle_image_event.py -v`
Expected: FAIL（目前 `handle_image_event` 會直接存檔，不會設定 `pending_backside_confirm` 狀態，`test_fresh_image_asks_about_backside_and_does_not_save` 會失敗）。

- [ ] **Step 3: 重寫 `handle_image_event`**

找到整段既有函式：

```python
async def handle_image_event(event: MessageEvent, user_id: str) -> None:
    message_content = await line_bot_api.get_message_content(event.message.id)
    image_content = b""
    async for s in message_content.iter_content():
        image_content += s
    img = PIL.Image.open(BytesIO(image_content))
    result = gemini_utils.generate_json_from_image(img, config.IMGAGE_PROMPT)
    card_obj = utils.parse_gemini_result_to_json(result.text)
    if not card_obj:
        error_msg = f"無法解析這張名片，請再試一次。 錯誤資訊: {result.text}"
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text=error_msg)]
        )
        return

    # Gemini Pro Vision API might return a list of objects, take the first one.
    if isinstance(card_obj, list):
        if not card_obj:
            error_msg = f"無法解析這張名片，Gemini 回傳了空的資料。 資訊: {result.text}"
            await line_bot_api.reply_message(
                event.reply_token,
                [TextSendMessage(text=error_msg)]
            )
            return
        card_obj = card_obj[0]

    card_obj = {k.lower(): v for k, v in card_obj.items()}

    existing_card_id = firebase_utils.check_if_card_exists(card_obj, user_id)
    if existing_card_id:
        existing_card_data = firebase_utils.get_card_by_id(
            user_id, existing_card_id)
        reply_msg = flex_messages.get_namecard_flex_msg(
            existing_card_data, existing_card_id)
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(
                text="這個名片已經存在資料庫中。",
                quick_reply=get_quick_reply_items()
            ), reply_msg],
        )
        return

    card_id = firebase_utils.add_namecard(card_obj, user_id)
    if card_id:
        reply_msg = flex_messages.get_namecard_flex_msg(card_obj, card_id)
        chinese_reply_msg = TextSendMessage(
            text="名片資料已經成功加入資料庫。",
            quick_reply=get_quick_reply_items()
        )
        await line_bot_api.reply_message(
            event.reply_token, [reply_msg, chinese_reply_msg])
    else:
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(
                text="儲存名片時發生錯誤。",
                quick_reply=get_quick_reply_items()
            )])
```

改成：

```python
async def handle_image_event(event: MessageEvent, user_id: str) -> None:
    message_content = await line_bot_api.get_message_content(event.message.id)
    image_content = b""
    async for s in message_content.iter_content():
        image_content += s
    img = PIL.Image.open(BytesIO(image_content))

    state = user_states.get(user_id, {})
    is_awaiting_backside = (
        state.get('action') == 'awaiting_backside_image'
        and state.get('expires_at', 0) > time.time()
    )

    if is_awaiting_backside:
        front_img = PIL.Image.open(BytesIO(state['front_image_bytes']))
        result = gemini_utils.generate_json_from_two_images(
            front_img, img, config.DOUBLE_SIDED_IMAGE_PROMPT)
        del user_states[user_id]
    else:
        # 只清除跟背面辨識流程有關的殘留狀態，
        # 不動其他無關的 pending 狀態（例如 adding_memo、editing_field）
        if state.get('action') in (
            'pending_backside_confirm', 'awaiting_backside_image'
        ):
            del user_states[user_id]
        result = gemini_utils.generate_json_from_image(
            img, config.IMGAGE_PROMPT)

    card_obj = utils.parse_gemini_result_to_json(result.text)
    if not card_obj:
        error_msg = f"無法解析這張名片，請再試一次。 錯誤資訊: {result.text}"
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text=error_msg)]
        )
        return

    # Gemini Pro Vision API might return a list of objects, take the first one.
    if isinstance(card_obj, list):
        if not card_obj:
            error_msg = f"無法解析這張名片，Gemini 回傳了空的資料。 資訊: {result.text}"
            await line_bot_api.reply_message(
                event.reply_token,
                [TextSendMessage(text=error_msg)]
            )
            return
        card_obj = card_obj[0]

    card_obj = {k.lower(): v for k, v in card_obj.items()}

    if is_awaiting_backside:
        await _finalize_and_save_card(card_obj, event, user_id)
        return

    user_states[user_id] = {
        'action': 'pending_backside_confirm',
        'card_obj': card_obj,
        'front_image_bytes': image_content,
        'expires_at': time.time() + PENDING_BACKSIDE_TIMEOUT_SECONDS
    }
    await line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text="📇 已辨識正面資料，這張名片還有背面嗎？",
            quick_reply=get_backside_confirm_quick_reply()
        )
    )
```

- [ ] **Step 4: 執行測試，確認通過**

Run: `pytest tests/test_handle_image_event.py -v`
Expected: PASS（4 個測試全過）

- [ ] **Step 5: 執行完整測試套件，確認沒有回歸**

Run: `pytest -v`
Expected: 全部 PASS（包含 Task 1-3 的測試）

- [ ] **Step 6: Lint 檢查**

Run: `flake8 app/line_handlers.py`
Expected: 無輸出

- [ ] **Step 7: Commit**

```bash
git add app/line_handlers.py tests/test_handle_image_event.py
git commit -m "feat: ask for backside image before saving namecard"
```

---

### Task 5: `handle_postback_event` — `backside_confirm` action

**Files:**
- Modify: `app/line_handlers.py`
- Test: `tests/test_handle_postback_backside.py`

**Interfaces:**
- Consumes: `_finalize_and_save_card`、`PENDING_BACKSIDE_TIMEOUT_SECONDS`（Task 3）
- Produces: `handle_postback_event` 新增對 `action=backside_confirm` 的處理（`has_backside=yes|no`），驗證 pending 狀態有效性與逾時。

- [ ] **Step 1: 寫失敗的測試**

建立 `tests/test_handle_postback_backside.py`：

```python
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
```

- [ ] **Step 2: 執行測試，確認失敗**

Run: `pytest tests/test_handle_postback_backside.py -v`
Expected: FAIL（目前 `handle_postback_event` 沒有 `backside_confirm` 分支，`postback_data.get('card_id')` 會是 `None`，最終會走到 `firebase_utils.get_name_from_card` 分支並回覆「找不到該名片資料」，斷言會失敗）。

- [ ] **Step 3: 新增 `backside_confirm` 分支**

找到：

```python
    elif action == 'cancel_update':
        if user_id in user_states:
            del user_states[user_id]
        await line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text='已取消修改操作。',
                quick_reply=get_quick_reply_items()
            )
        )
        return

    # 處理需要 card_id 的 action
    card_name = firebase_utils.get_name_from_card(user_id, card_id)
```

改成：

```python
    elif action == 'cancel_update':
        if user_id in user_states:
            del user_states[user_id]
        await line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text='已取消修改操作。',
                quick_reply=get_quick_reply_items()
            )
        )
        return

    elif action == 'backside_confirm':
        has_backside = postback_data.get('has_backside')
        state = user_states.get(user_id, {})
        is_valid = (
            state.get('action') == 'pending_backside_confirm'
            and state.get('expires_at', 0) > time.time()
        )
        if not is_valid:
            if user_id in user_states:
                del user_states[user_id]
            await line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text='沒有待確認的名片資料，或操作已過期，'
                         '請重新傳送名片圖片。',
                    quick_reply=get_quick_reply_items()
                )
            )
            return

        if has_backside == 'yes':
            user_states[user_id] = {
                'action': 'awaiting_backside_image',
                'front_image_bytes': state['front_image_bytes'],
                'expires_at': (
                    time.time() + PENDING_BACKSIDE_TIMEOUT_SECONDS
                )
            }
            await line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text='請傳送背面照片 📸')
            )
        else:
            del user_states[user_id]
            await _finalize_and_save_card(
                state['card_obj'], event, user_id)
        return

    # 處理需要 card_id 的 action
    card_name = firebase_utils.get_name_from_card(user_id, card_id)
```

- [ ] **Step 4: 執行測試，確認通過**

Run: `pytest tests/test_handle_postback_backside.py -v`
Expected: PASS

- [ ] **Step 5: 執行完整測試套件**

Run: `pytest -v`
Expected: 全部 PASS

- [ ] **Step 6: Lint 檢查**

Run: `flake8 app/line_handlers.py`
Expected: 無輸出

- [ ] **Step 7: Commit**

```bash
git add app/line_handlers.py tests/test_handle_postback_backside.py
git commit -m "feat: handle backside_confirm postback action"
```

---

### Task 6: `handle_text_event` — 文字打斷時清除背面等待狀態

**Files:**
- Modify: `app/line_handlers.py`
- Test: `tests/test_handle_text_interrupt.py`

**Interfaces:**
- Consumes: `handle_smart_query`（既有函式，測試中會被 mock）
- Produces: `handle_text_event` 在偵測到 `user_action` 為 `pending_backside_confirm` 或 `awaiting_backside_image` 時，清除該 state 並照常往下走既有邏輯（不強迫使用者完成背面流程）。

- [ ] **Step 1: 寫失敗的測試**

建立 `tests/test_handle_text_interrupt.py`：

```python
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
```

- [ ] **Step 2: 執行測試，確認失敗**

Run: `pytest tests/test_handle_text_interrupt.py -v`
Expected: FAIL（目前 `handle_text_event` 不認得 `pending_backside_confirm` / `awaiting_backside_image`，會直接落到 `else: await handle_smart_query(...)` 分支——`mock_query.assert_awaited_once_with(...)` 可能仍會過，但 `assert "user-1" not in line_handlers.user_states` 會失敗，因為舊 state 沒被清掉）。

- [ ] **Step 3: 修改 `handle_text_event`**

找到：

```python
async def handle_text_event(event: MessageEvent, user_id: str) -> None:
    msg = event.message.text
    user_action = user_states.get(user_id, {}).get('action')

    if user_action == 'adding_memo':
```

改成：

```python
async def handle_text_event(event: MessageEvent, user_id: str) -> None:
    msg = event.message.text
    user_action = user_states.get(user_id, {}).get('action')

    if user_action in (
        'pending_backside_confirm', 'awaiting_backside_image'
    ):
        del user_states[user_id]
        user_action = None

    if user_action == 'adding_memo':
```

- [ ] **Step 4: 執行測試，確認通過**

Run: `pytest tests/test_handle_text_interrupt.py -v`
Expected: PASS

- [ ] **Step 5: 執行完整測試套件（全功能回歸）**

Run: `pytest -v`
Expected: 全部 PASS

- [ ] **Step 6: Lint 檢查（全專案）**

Run: `flake8 .`
Expected: 無輸出

- [ ] **Step 7: Commit**

```bash
git add app/line_handlers.py tests/test_handle_text_interrupt.py
git commit -m "fix: clear pending backside state when interrupted by text"
```

---

## 手動驗證（選用，需要真實 GCP 憑證）

自動化測試全數使用 mock，不會打真實 Gemini API。若要在合併前用真實名片圖片人工驗證合併效果，可比照 `scratch/test_gemini_schema.py` 的模式，另外寫一個 `scratch/test_double_sided_merge.py`：用 PIL 產生一張含中文的假名片圖與一張含英文的假名片圖，呼叫 `gemini_utils.generate_json_from_two_images`，肉眼檢查合併後的 JSON 是否符合預期（例如 `name` 欄位是否正確合併中英文）。此腳本不需要、也不應該被排進本計畫的自動化任務或 CI，僅供本地手動抽測。
