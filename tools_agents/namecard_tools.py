import os
import json
from io import BytesIO
import PIL.Image
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv
import google.generativeai as genai

# LINE SDK Imports
from linebot import LineBotApi
from linebot.models import TextSendMessage, FlexSendMessage
# from linebot.exceptions import LineBotApiError # For more specific error handling if needed

# Load environment variables from .env file
load_dotenv()

# Configure Gemini API Key
gemini_api_key = os.getenv("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    print("Gemini API Key configured successfully for namecard_tools.")
else:
    print(
        "GEMINI_API_KEY not found in environment variables. Gemini tools may not function."
    )

# Configure LINE Channel Access Token
CHANNEL_ACCESS_TOKEN = os.getenv("ChannelAccessToken")
if not CHANNEL_ACCESS_TOKEN:
    print(
        "ChannelAccessToken not found in environment variables. LINE tools may not function."
    )

# Firebase Path
NAMECARD_DB_PATH = "namecard"

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    try:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {"databaseURL": os.getenv("FIREBASE_URL")})
        print("Firebase Admin SDK initialized successfully for namecard_tools.")
    except Exception as e:
        print(f"Error initializing Firebase Admin SDK for namecard_tools: {e}")

# Prompts (copied from main.py)
IMGAGE_PROMPT = """
這是一張名片，你是一個名片秘書。請將以下資訊整理成 json 給我。
如果看不出來的，幫我填寫 N/A
只好 json 就好:
name, title, address, email, phone, company.
其中 phone 的內容格式為 #886-0123-456-789,1234. 沒有分機就忽略 ,1234
"""

QUERY_PROMPT = """
這是所有的名片資料，請根據輸入文字來查詢相關的名片資料 {all_cards}，
例如: 名字, 職稱, 公司名稱。 查詢問句為： {msg}, 只要回覆我找到的 JSON Data 就好。
"""


# =====================
# Firebase Tools
# =====================
def get_all_cards_tool(user_id: str) -> dict:
    """
    Retrieves all namecard data for a given user_id from Firebase Realtime Database.
    Args: user_id: The unique identifier for the user.
    Returns: Dict of namecards or empty dict.
    """
    print(
        f"Calling get_all_cards_tool for user_id: {user_id}, DB Path: {NAMECARD_DB_PATH}/{user_id}"
    )
    try:
        ref = db.reference(f"{NAMECARD_DB_PATH}/{user_id}")
        namecard_data = ref.get()
        return namecard_data or {}
    except Exception as e:
        print(f"Error fetching namecards for user {user_id}: {e}")
        return {}


def add_namecard_tool(user_id: str, namecard_data: dict) -> str:
    """
    Adds a new namecard to Firebase.
    Args: user_id, namecard_data (dict).
    Returns: Status message string.
    """
    print(f"Calling add_namecard_tool for user_id: {user_id}")
    if not user_id:
        return "Failed: user_id empty."
    if not namecard_data or not isinstance(namecard_data, dict):
        return "Failed: namecard_data invalid."
    try:
        ref = db.reference(f"{NAMECARD_DB_PATH}/{user_id}")
        ref.push(namecard_data)
        return "Namecard added successfully."
    except Exception as e:
        print(f"Error adding namecard for user {user_id}: {e}")
        return f"Failed to add namecard: {e}"


def remove_redundant_data_tool(user_id: str) -> str:
    """
    Removes namecards with redundant email addresses for a user.
    Args: user_id.
    Returns: Status message string.
    """
    print(f"Calling remove_redundant_data_tool for user_id: {user_id}")
    try:
        ref = db.reference(f"{NAMECARD_DB_PATH}/{user_id}")
        namecard_data = ref.get()
        if not namecard_data:
            return "No namecards found."
        email_map, keys_to_delete = {}, []
        for key, value in namecard_data.items():
            email = value.get("email")
            if email:
                if email in email_map:
                    keys_to_delete.append(key)
                else:
                    email_map[email] = key
        if not keys_to_delete:
            return "No redundant namecards found."
        for key in keys_to_delete:
            ref.child(key).delete()
        return (
            f"Redundant data removal complete. {len(keys_to_delete)} card(s) removed."
        )
    except Exception as e:
        print(f"Error removing redundant data for user {user_id}: {e}")
        return f"Failed to remove redundant data: {e}"


def check_if_card_exists_tool(user_id: str, namecard_data: dict) -> bool:
    """
    Checks if a namecard (by email) exists in Firebase.
    Args: user_id, namecard_data (must contain 'email').
    Returns: True if exists, False otherwise.
    """
    print(f"Calling check_if_card_exists_tool for user_id: {user_id}")
    try:
        email_to_check = namecard_data.get("email")
        if not email_to_check:
            print("Warning: check_if_card_exists_tool no email.")
            return False
        all_cards = get_all_cards_tool(user_id)
        if all_cards:
            for card_details in all_cards.values():
                if card_details.get("email") == email_to_check:
                    return True
        return False
    except Exception as e:
        print(
            f"Error checking if namecard exists for {user_id} with email {namecard_data.get('email')}: {e}"
        )
        return False


# =====================
# Gemini Tools
# =====================
def parse_namecard_from_image_tool(image_bytes: bytes) -> dict:
    """
    Parses namecard info from image bytes using Gemini. Not intended for direct agent use.
    Args: image_bytes.
    Returns: Parsed namecard dict or {"error": ...}.
    """
    print("Calling parse_namecard_from_image_tool")
    if not gemini_api_key:
        return {"error": "Gemini API key not configured."}
    if not image_bytes:
        return {"error": "Image bytes cannot be empty."}
    try:
        img = PIL.Image.open(BytesIO(image_bytes))
    except Exception as e:
        return {"error": f"Failed to open image: {e}"}
    try:
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        model = genai.GenerativeModel(
            model_name, generation_config={"response_mime_type": "application/json"}
        )
        response = model.generate_content([IMGAGE_PROMPT, img], stream=True)
        response.resolve()
        if not response.text:
            return {"error": "Gemini returned empty response."}
        card_obj = json.loads(response.text)
        return {k.lower(): v for k, v in card_obj.items()}
    except json.JSONDecodeError:
        return {
            "error": "Failed to parse JSON from Gemini.",
            "details": response.text if "response" in locals() else "No response text",
        }
    except Exception as e:
        error_details = str(e)
        if "response" in locals() and hasattr(response, "prompt_feedback"):
            error_details += f" | PF: {response.prompt_feedback}"
        return {"error": "Gemini content generation failed.", "details": error_details}


def query_namecards_tool(user_id: str, user_query: str, all_cards_list: list) -> list:
    """
    Queries a list of namecards using Gemini based on user's text query.
    The user_id is included for context but the primary inputs for querying are user_query and all_cards_list.
    Args: user_id, user_query, all_cards_list (list of dicts).
    Returns: List of matching namecards or empty list.
    """
    print(
        f"Calling query_namecards_tool for user_id: {user_id} with query: {user_query}"
    )
    if not gemini_api_key:
        print("Gemini key not configured.")
        return []
    if not user_query or not all_cards_list:
        return []
    try:
        # user_id might be used in the future to personalize the query_prompt if needed
        all_cards_json_str = json.dumps(all_cards_list, ensure_ascii=False)
        formatted_prompt = QUERY_PROMPT.format(
            all_cards=all_cards_json_str, msg=user_query
        )
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        model = genai.GenerativeModel(
            model_name, generation_config={"response_mime_type": "application/json"}
        )
        response = model.generate_content(
            [{"role": "user", "parts": [formatted_prompt]}]
        )
        if not response.text:
            print("Gemini query response empty.")
            return []
        parsed_response = json.loads(response.text)
        if isinstance(parsed_response, dict):
            return [parsed_response]
        elif isinstance(parsed_response, list):
            return parsed_response
        else:
            print(f"Unexpected Gemini query response format: {type(parsed_response)}")
            return []
    except json.JSONDecodeError:
        print(
            f"JSON parsing failed for query. Response: {response.text if 'response' in locals() else 'No response'}"
        )
        return []
    except Exception as e:
        error_details = str(e)
        if "response" in locals() and hasattr(response, "prompt_feedback"):
            error_details += f" | PF: {response.prompt_feedback}"
        print(
            f"Error querying namecards with Gemini for user {user_id}: {error_details}"
        )
        return []


# =====================
# LINE Communication Tools
# =====================


def format_namecard_flex_content(card_data: dict) -> dict:
    """
    Formats the content for a LINE Flex Message representing a namecard.
    This is a helper function, not intended for direct agent use, but used by send_flex_message_tool.
    Args: card_data (dict): A dictionary containing namecard information.
    Returns: dict: The content structure for a FlexSendMessage.
    """
    print("Calling format_namecard_flex_content")
    return {
        "type": "bubble",
        "size": "giga",
        "body": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "md",
            "contents": [
                {
                    "type": "image",
                    "aspectMode": "cover",
                    "aspectRatio": "1:1",
                    "flex": 1,
                    "size": "full",
                    "url": card_data.get(
                        "image_url",
                        "https://raw.githubusercontent.com/kkdai/linebot-smart-namecard/main/img/logo.jpeg",
                    ),
                },
                {
                    "type": "box",
                    "flex": 4,
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "align": "end",
                            "size": "xxl",
                            "text": str(card_data.get("name", "N/A")),
                            "weight": "bold",
                        },
                        {
                            "type": "text",
                            "align": "end",
                            "size": "sm",
                            "text": str(card_data.get("title", "N/A")),
                        },
                        {
                            "type": "text",
                            "align": "end",
                            "margin": "xxl",
                            "size": "lg",
                            "text": str(card_data.get("company", "N/A")),
                            "weight": "bold",
                        },
                        {
                            "type": "text",
                            "align": "end",
                            "size": "sm",
                            "text": str(card_data.get("address", "N/A")),
                        },
                        {
                            "type": "text",
                            "align": "end",
                            "margin": "xxl",
                            "text": str(card_data.get("phone", "N/A")),
                        },
                        {
                            "type": "text",
                            "align": "end",
                            "text": str(card_data.get("email", "N/A")),
                        },
                    ],
                },
            ],
        },
        "styles": {"footer": {"separator": True}},
    }


def send_text_message_tool(user_id: str, message_text: str) -> str:
    """
    Sends a text message to a specified LINE user.
    Args: user_id, message_text.
    Returns: Status string.
    """
    print(f"Calling send_text_message_tool for user_id: {user_id}")
    if not CHANNEL_ACCESS_TOKEN:
        return "Failed: ChannelAccessToken not configured."
    if not user_id:
        return "Failed: user_id empty."
    if not message_text:
        return "Failed: message_text empty."
    try:
        line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
        line_bot_api.push_message(user_id, TextSendMessage(text=message_text))
        return "Text message sent successfully."
    except Exception as e:
        print(f"Error sending LINE text message to {user_id}: {e}")
        return f"Failed to send text message: {e}"


def send_flex_message_tool(
    user_id: str, alt_text: str, namecard_data_for_flex: dict
) -> str:
    """
    Sends a Flex Message to a LINE user, formatting the content using namecard_data_for_flex.
    Args: user_id, alt_text, namecard_data_for_flex (dict for the card to be displayed).
    Returns: Status string.
    """
    print(f"Calling send_flex_message_tool for user_id: {user_id}")
    if not CHANNEL_ACCESS_TOKEN:
        return "Failed: ChannelAccessToken not configured."
    if not user_id:
        return "Failed: user_id empty."
    if not alt_text:
        return "Failed: alt_text empty."
    if not namecard_data_for_flex or not isinstance(namecard_data_for_flex, dict):
        return "Failed: namecard_data_for_flex must be a non-empty dictionary."
    try:
        line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
        # Use format_namecard_flex_content to create the contents
        flex_message_contents = format_namecard_flex_content(namecard_data_for_flex)
        message = FlexSendMessage(alt_text=alt_text, contents=flex_message_contents)
        line_bot_api.push_message(user_id, message)
        return "Flex message sent successfully."
    except Exception as e:
        print(f"Error sending LINE flex message to {user_id}: {e}")
        return f"Failed to send flex message: {e}"


# =====================
# Other Tools
# =====================
def generate_sample_namecard_tool() -> dict:
    """
    Generates a sample namecard dictionary. Requires no arguments.
    This tool is for testing or demonstration purposes.
    Returns: A dictionary representing a sample namecard.
    """
    print("Calling generate_sample_namecard_tool")
    return {
        "name": "Sample Card-Owner",
        "title": "Chief Example Officer",
        "address": "123 Demo St, Testville, EX 45678",
        "email": "sample.owner@example.com",
        "phone": "+1-555-0100-123",  # Ensure phone format matches expected by Gemini if any
        "company": "Examples Inc.",
        "image_url": "https://raw.githubusercontent.com/kkdai/linebot-smart-namecard/main/img/logo.jpeg",  # Optional: for flex message display
    }


# Conceptual list of tools for agent registration
# parse_namecard_from_image_tool is NOT for agent use.
# format_namecard_flex_content is a helper, NOT for agent use.
agent_tool_list = [
    get_all_cards_tool,
    add_namecard_tool,
    remove_redundant_data_tool,
    check_if_card_exists_tool,
    query_namecards_tool,
    send_text_message_tool,
    send_flex_message_tool,
    generate_sample_namecard_tool,
]


if __name__ == "__main__":
    print(
        "\nRunning namecard_tools.py directly for testing (requires Firebase, Gemini & LINE setup)."
    )
    test_user_id = os.getenv("TEST_LINE_USER_ID", "test_user_tools_123")

    # --- Test generate_sample_namecard_tool ---
    print("\n--- Testing generate_sample_namecard_tool ---")
    sample_card = generate_sample_namecard_tool()
    print(f"Generated sample card: {json.dumps(sample_card, indent=2)}")
    if sample_card and sample_card.get("name") == "Sample Card-Owner":
        print("generate_sample_namecard_tool seems to work correctly.")
    else:
        print("generate_sample_namecard_tool output is unexpected.")

    # --- LINE Tool Tests (modified to use the sample card) ---
    print("\n--- Testing LINE Tools with Sample Card ---")
    if not CHANNEL_ACCESS_TOKEN:
        print("Skipping LINE tool tests as ChannelAccessToken is not set.")
    else:
        print(f"Attempting LINE tool tests with user_id: {test_user_id}")
        # Test send_text_message_tool
        if test_user_id != "test_user_tools_123":
            text_send_status = send_text_message_tool(
                test_user_id,
                f"Test from namecard_tools.py: This is a sample card: {sample_card.get('name')}",
            )
            print(f"Send text message status: {text_send_status}")
        else:
            print(
                "Skipping actual send_text_message_tool call to dummy user_id for sample card text."
            )

        # Test send_flex_message_tool with the generated sample card
        if test_user_id != "test_user_tools_123" and sample_card:
            # The send_flex_message_tool now takes the card data directly
            flex_send_status = send_flex_message_tool(
                test_user_id, f"Sample Card: {sample_card.get('name')}", sample_card
            )
            print(f"Send flex message (sample card) status: {flex_send_status}")
        else:
            print(
                "Skipping actual send_flex_message_tool call to dummy user_id for sample card flex."
            )

    print("\n--- Previous Firebase/Gemini tests can be run here if needed ---")
    # (Consider re-adding some if you test this file standalone frequently)

    print("\n--- End of Tests for namecard_tools.py ---")
