from linebot.models import FlexSendMessage


def get_namecard_flex_msg(card_data: dict, card_id: str) -> FlexSendMessage:
    # 確保基本資料存在
    name = card_data.get("name", "N/A")
    title = card_data.get("title", "N/A")
    company = card_data.get("company", "N/A")
    address = card_data.get("address", "N/A")
    phone = card_data.get("phone", "N/A")
    email = card_data.get("email", "N/A")
    memo = card_data.get("memo", "")  # 讀取備忘錄

    flex_msg = {
        "type": "bubble",
        "size": "giga",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": company,
                         "color": "#ffffff", "size": "lg"},
                        {"type": "text", "text": name, "color": "#ffffff",
                         "size": "xxl", "weight": "bold"},
                        {"type": "text", "text": title,
                         "color": "#ffffff", "size": "md"},
                    ]
                }
            ],
            "paddingAll": "20px",
            "backgroundColor": "#0367D3",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "box", "layout": "horizontal", "margin": "md",
                 "contents": [
                     {"type": "text", "text": "Phone", "size": "sm",
                      "color": "#555555", "flex": 1},
                     {"type": "text", "text": phone, "size": "sm",
                      "color": "#111111", "align": "end", "flex": 3}
                 ]},
                {"type": "box", "layout": "horizontal", "margin": "md",
                 "contents": [
                     {"type": "text", "text": "Email", "size": "sm",
                      "color": "#555555", "flex": 1},
                     {"type": "text", "text": email, "size": "sm",
                      "color": "#111111", "align": "end", "flex": 3}
                 ]},
                {"type": "box", "layout": "horizontal", "margin": "md",
                 "contents": [
                     {"type": "text", "text": "Address",
                      "size": "sm", "color": "#555555", "flex": 1},
                     {"type": "text",
                      "text": address,
                      "size": "sm",
                      "color": "#111111",
                      "align": "end",
                      "wrap": True,
                      "flex": 3}
                 ]},
                {"type": "separator", "margin": "xxl"},
                {"type": "box", "layout": "vertical", "margin": "md",
                 "contents": [
                     {"type": "text", "text": "備忘錄",
                      "size": "md", "color": "#555555"},
                     {"type": "text",
                      "text": memo or "尚無備忘錄",
                      "color": "#111111",
                      "size": "sm",
                      "wrap": True,
                      "margin": "md"}
                 ]}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "style": "link",
                            "height": "sm",
                            "action": {
                                "type": "postback",
                                "label": "新增/修改記事",
                                "data": f"action=add_memo&card_id={card_id}",
                                "displayText": f"我想為 {name} 新增記事"
                            },
                            "flex": 1
                        },
                        {
                            "type": "button",
                            "style": "link",
                            "height": "sm",
                            "action": {
                                "type": "postback",
                                "label": "編輯資料",
                                "data": f"action=edit_card&card_id={card_id}",
                                "displayText": f"我想編輯 {name} 的名片"
                            },
                            "flex": 1
                        }
                    ]
                },
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "📥 加入通訊錄",
                        "data": f"action=download_contact&card_id={card_id}",
                        "displayText": f"下載 {name} 的聯絡人資訊"
                    },
                    "margin": "sm"
                }
            ]
        },
        "styles": {
            "footer": {
                "separator": True,
            }
        },
    }

    return FlexSendMessage(alt_text=f"{name} 的名片", contents=flex_msg)


def get_edit_options_flex_msg(card_id: str, card_name: str) -> FlexSendMessage:
    """產生一個包含所有可編輯欄位的 Flex Message"""
    fields = [
        ("姓名", "name"), ("職稱", "title"), ("公司", "company"),
        ("地址", "address"), ("電話", "phone"), ("Email", "email")
    ]
    buttons = []
    for label, field_key in fields:
        display_text = f"我想修改 {card_name} 的 {label}"
        buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": label,
                "data": (f"action=edit_field&card_id={card_id}"
                         f"&field={field_key}"),
                "displayText": display_text
            },
            "style": "primary",
            "margin": "sm"
        })

    flex_msg = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"請問您想編輯「{card_name}」的哪個欄位？",
                    "weight": "bold",
                    "size": "lg",
                    "wrap": True
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "spacing": "sm",
                    "contents": buttons
                }
            ]
        }
    }

    return FlexSendMessage(
        alt_text=f"編輯 {card_name} 的資料",
        contents=flex_msg
    )