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


def get_namecard_list_flex_msg(
    cards: list, title_text: str = "🔍 找到多個相符的名片"
) -> FlexSendMessage:
    """產生一個包含聯絡人清單的 Flex Message，點擊其中一筆可顯示詳細名片卡片。"""
    contents = []

    # 限制清單最多顯示 8 筆，確保符合 LINE 訊息長度限制
    for card in cards[:8]:
        card_id = card.get("card_id")
        name = card.get("name", "N/A")
        company = card.get("company", "N/A")
        title = card.get("title", "N/A")

        info_text = company
        if title and title != "N/A":
            info_text = f"{company} | {title}"

        contents.append({
            "type": "box",
            "layout": "horizontal",
            "paddingAll": "10px",
            "action": {
                "type": "postback",
                "label": f"顯示 {name}",
                "data": f"action=show_card&card_id={card_id}",
                "displayText": f"我想看 {name} 的名片"
            },
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "flex": 4,
                    "contents": [
                        {
                            "type": "text",
                            "text": name,
                            "weight": "bold",
                            "size": "md",
                            "color": "#111111"
                        },
                        {
                            "type": "text",
                            "text": info_text,
                            "size": "xs",
                            "color": "#555555",
                            "margin": "xs",
                            "wrap": True
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "flex": 1,
                    "justifyContent": "center",
                    "alignItems": "flex-end",
                    "contents": [
                        {
                            "type": "text",
                            "text": "查看 ❯",
                            "size": "xs",
                            "color": "#0367D3",
                            "weight": "bold"
                        }
                    ]
                }
            ]
        })
        contents.append({"type": "separator"})

    if contents:
        contents.pop()  # 移除最後一條分隔線

    flex_msg = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": title_text,
                    "weight": "bold",
                    "size": "lg",
                    "color": "#0367D3"
                },
                {
                    "type": "text",
                    "text": (
                        f"共找到 {len(cards)} 筆相符資料，"
                        "請點選要查看的名片："
                    ),
                    "size": "xs",
                    "color": "#888888",
                    "margin": "sm"
                },
                {"type": "separator", "margin": "md"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "contents": contents
                }
            ]
        }
    }

    return FlexSendMessage(alt_text=title_text, contents=flex_msg)


def get_confirm_update_flex_msg(
    message_text: str, confirm_data: str, cancel_data: str
) -> FlexSendMessage:
    """產生一個用於確認修改動作的 Flex Message Bubble"""
    flex_msg = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "⚠️ 確認修改資料",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#D32F2F"
                },
                {
                    "type": "text",
                    "text": message_text,
                    "size": "md",
                    "margin": "md",
                    "wrap": True,
                    "color": "#333333"
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#D32F2F",
                    "action": {
                        "type": "postback",
                        "label": "確定修改",
                        "data": confirm_data,
                        "displayText": "確定修改"
                    }
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "postback",
                        "label": "取消",
                        "data": cancel_data,
                        "displayText": "取消修改"
                    }
                }
            ]
        }
    }
    return FlexSendMessage(alt_text="確認修改資料", contents=flex_msg)
