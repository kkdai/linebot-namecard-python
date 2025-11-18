from urllib.parse import parse_qsl
from linebot.models import (
    PostbackEvent, MessageEvent, TextSendMessage, ImageSendMessage,
    QuickReply, QuickReplyButton, PostbackAction
)
from io import BytesIO
import PIL.Image
import json

from . import firebase_utils, gemini_utils, utils, flex_messages, config, qrcode_utils
from .bot_instance import line_bot_api, user_states

FIELD_LABELS = {
    "name": "姓名", "title": "職稱", "company": "公司",
    "address": "地址", "phone": "電話", "email": "Email"
}


def get_quick_reply_items():
    """建立常用功能的 Quick Reply 按鈕"""
    return QuickReply(items=[
        QuickReplyButton(
            action=PostbackAction(
                label="📊 統計",
                data="action=show_stats"
            )
        ),
        QuickReplyButton(
            action=PostbackAction(
                label="📋 列表",
                data="action=show_list"
            )
        ),
        QuickReplyButton(
            action=PostbackAction(
                label="🧪 測試",
                data="action=show_test"
            )
        ),
        QuickReplyButton(
            action=PostbackAction(
                label="ℹ️ 說明",
                data="action=show_help"
            )
        )
    ])


async def handle_postback_event(event: PostbackEvent, user_id: str):
    postback_data = dict(parse_qsl(event.postback.data))
    action = postback_data.get('action')
    card_id = postback_data.get('card_id')

    # 處理功能性 action（不需要 card_id）
    if action == 'show_stats':
        stats = firebase_utils.get_namecard_statistics(user_id)
        stats_text = f"""📊 名片統計資訊

📇 總名片數：{stats['total']} 張
📅 本月新增：{stats['this_month']} 張
🏢 最常合作公司：{stats['top_company']}"""
        await line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=stats_text, quick_reply=get_quick_reply_items())
        )
        return

    elif action == 'show_list':
        all_cards = firebase_utils.get_all_cards(user_id)
        list_text = f"📋 總共有 {len(all_cards)} 張名片資料。"
        await line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=list_text, quick_reply=get_quick_reply_items())
        )
        return

    elif action == 'show_test':
        test_namecard = utils.generate_sample_namecard()
        reply_card_msg = flex_messages.get_namecard_flex_msg(
            test_namecard, "test_card_id")
        await line_bot_api.reply_message(event.reply_token, [reply_card_msg])
        return

    elif action == 'show_help':
        help_text = """ℹ️ 名片管理機器人使用說明

📸 上傳名片圖片 → 自動辨識並儲存
🔍 輸入文字 → 智能搜尋相關名片
📊 統計 → 查看名片統計資訊
📋 列表 → 顯示名片總數
🧪 測試 → 查看範例名片

💡 小提示：
• 點擊名片可以編輯、加入備註
• 使用「加入通訊錄」可下載 QR Code"""
        await line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=help_text, quick_reply=get_quick_reply_items())
        )
        return

    # 處理需要 card_id 的 action
    card_name = firebase_utils.get_name_from_card(user_id, card_id)
    if not card_name:
        await line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text='找不到該名片資料。'))
        return

    if action == 'add_memo':
        user_states[user_id] = {'action': 'adding_memo', 'card_id': card_id}
        reply_text = f"請輸入關於「{card_name}」的備忘錄："
        await line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text=reply_text))

    elif action == 'edit_card':
        reply_msg = flex_messages.get_edit_options_flex_msg(card_id, card_name)
        await line_bot_api.reply_message(event.reply_token, [reply_msg])

    elif action == 'edit_field':
        field_to_edit = postback_data.get('field')
        field_label = FIELD_LABELS.get(field_to_edit, "資料")
        user_states[user_id] = {
            'action': 'editing_field',
            'card_id': card_id,
            'field': field_to_edit
        }
        reply_text = f"請輸入「{card_name}」的新「{field_label}」："
        await line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text=reply_text))

    elif action == 'download_contact':
        await handle_download_contact(event, user_id, card_id, card_name)


async def handle_download_contact(
        event: PostbackEvent, user_id: str, card_id: str, card_name: str):
    """處理下載聯絡人 QR Code 的請求"""
    try:
        # 從 Firebase 取得完整的名片資料
        card_data = firebase_utils.get_card_by_id(user_id, card_id)
        if not card_data:
            await line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text='找不到該名片資料。'))
            return

        # 生成 vCard QR Code
        qrcode_image = qrcode_utils.generate_vcard_qrcode(card_data)

        # 上傳到 Firebase Storage 並取得 URL
        image_url = firebase_utils.upload_qrcode_to_storage(
            qrcode_image, user_id, card_id)

        if not image_url:
            await line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text='生成 QR Code 時發生錯誤，請稍後再試。'))
            return

        # 生成使用說明
        instruction_text = qrcode_utils.get_qrcode_usage_instruction(card_name)

        # 回傳 QR Code 圖片和使用說明
        image_message = ImageSendMessage(
            original_content_url=image_url,
            preview_image_url=image_url
        )
        text_message = TextSendMessage(text=instruction_text)

        await line_bot_api.reply_message(
            event.reply_token,
            [image_message, text_message])

    except Exception as e:
        print(f"Error in handle_download_contact: {e}")
        await line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='處理您的請求時發生錯誤，請稍後再試。'))


async def handle_text_event(event: MessageEvent, user_id: str) -> None:
    msg = event.message.text
    user_action = user_states.get(user_id, {}).get('action')

    if user_action == 'adding_memo':
        await handle_add_memo_state(event, user_id, msg)
    elif user_action == 'editing_field':
        await handle_edit_field_state(event, user_id, msg)
    elif msg == "remove":
        firebase_utils.remove_redundant_data(user_id)
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(
                text="Redundant data removal complete.",
                quick_reply=get_quick_reply_items()
            )],
        )
    else:
        await handle_smart_query(event, user_id, msg)


async def handle_add_memo_state(event: MessageEvent, user_id: str, msg: str):
    state = user_states[user_id]
    card_id = state['card_id']

    if firebase_utils.update_namecard_memo(card_id, user_id, msg):
        await line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text='備忘錄已成功更新！',
                quick_reply=get_quick_reply_items()
            ))
    else:
        await line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text='新增備忘錄時發生錯誤，請稍後再試。',
                quick_reply=get_quick_reply_items()
            ))
    del user_states[user_id]


async def handle_edit_field_state(event: MessageEvent, user_id: str, msg: str):
    state = user_states[user_id]
    card_id = state['card_id']
    field = state['field']

    if firebase_utils.update_namecard_field(user_id, card_id, field, msg):
        updated_card = firebase_utils.get_card_by_id(user_id, card_id)
        if updated_card:
            reply_msg = flex_messages.get_namecard_flex_msg(
                updated_card, card_id)
            await line_bot_api.reply_message(
                event.reply_token,
                [TextSendMessage(
                    text='資料已成功更新！',
                    quick_reply=get_quick_reply_items()
                ), reply_msg]
            )
        else:
            await line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text='資料更新成功，但無法立即顯示。',
                    quick_reply=get_quick_reply_items()
                ))
    else:
        await line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text='更新資料時發生錯誤，請稍後再試。',
                quick_reply=get_quick_reply_items()
            ))
    del user_states[user_id]


async def handle_smart_query(event: MessageEvent, user_id: str, msg: str):
    all_cards_dict = firebase_utils.get_all_cards(user_id)
    if not all_cards_dict:
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(
                text="您尚未建立任何名片。",
                quick_reply=get_quick_reply_items()
            )])
        return

    all_cards_list = []
    for card_id, card_data in all_cards_dict.items():
        card_data_with_id = card_data.copy()
        card_data_with_id['card_id'] = card_id
        all_cards_list.append(card_data_with_id)

    smart_query_prompt = (
        "你是一個名片助理，以下是所有名片資料（JSON 陣列），"
        "請根據使用者輸入的查詢，回傳最相關的一或多張名片 JSON"
        "（只回傳 JSON 陣列，不要多餘說明）。"
        "每張名片物件中都要包含 'card_id'.\n"
        f"名片資料: {json.dumps(all_cards_list, ensure_ascii=False)}\n"
        f"查詢: {msg}"
    )
    messages = [{"role": "user", "parts": [smart_query_prompt]}]

    try:
        response = gemini_utils.generate_gemini_text_complete(messages)
        card_objs = utils.load_json_string_to_object(response.text)
        if isinstance(card_objs, dict):
            card_objs = [card_objs]

        reply_msgs = []
        if card_objs:
            for card_obj in card_objs[:5]:
                card_id = card_obj.get("card_id")
                if card_id:
                    reply_msgs.append(
                        flex_messages.get_namecard_flex_msg(
                            card_obj, card_id))

        if reply_msgs:
            await line_bot_api.reply_message(event.reply_token, reply_msgs)
        else:
            await line_bot_api.reply_message(
                event.reply_token,
                [TextSendMessage(
                    text="查無相關名片資料。",
                    quick_reply=get_quick_reply_items()
                )],
            )

    except Exception as e:
        print(f"Error processing LLM response: {e}")
        await line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text="處理您的查詢時發生錯誤，請稍後再試。")],
        )


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