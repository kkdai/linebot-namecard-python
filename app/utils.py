import json


def load_json_string_to_object(json_str: str) -> dict:
    try:
        # 移除前後可能存在的 markdown 標籤
        json_str = json_str.strip().replace(
            "```json", "").replace(
            "```", "").strip()
        return json.loads(json_str)
    except Exception as e:
        print(f"Error loading JSON string: {e}, string was: {json_str}")
        return {}


def parse_gemini_result_to_json(card_json_str: str) -> dict:
    try:
        return json.loads(card_json_str)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return {}


def generate_sample_namecard() -> dict:
    return {
        "name": "Kevin Dai",
        "title": "Software Engineer",
        "address": "Taipei, Taiwan",
        "email": "aa@bbb.cc",
        "phone": "+886-123-456-789",
        "company": "LINE Taiwan",
        "memo": "This is a test memo."
    }
