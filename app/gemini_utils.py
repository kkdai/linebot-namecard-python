import vertexai
from vertexai.generative_models import GenerativeModel, Part
import PIL.Image
from io import BytesIO
from . import config

# Initialize Vertex AI
vertexai.init(project=config.PROJECT_ID, location=config.LOCATION)


def pil_to_bytes(img: PIL.Image.Image) -> bytes:
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG')
    return img_byte_arr.getvalue()


def generate_gemini_text_complete(messages: list) -> object:
    """Gemini 文字生成，強制要求結構化 JSON 輸出"""
    model = GenerativeModel(
        "gemini-3-flash-preview",
        generation_config={"response_mime_type": "application/json"},
    )
    # Convert list of dicts message format to prompt string if needed
    # line_handlers.py sends [{"role": "user", "parts": [smart_query_prompt]}]
    prompt = messages[0]["parts"][0]
    response = model.generate_content(prompt)
    return response


NAMECARD_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": {
            "type": "STRING",
            "description": "聯絡人姓名，如果看不出來，請填寫 N/A"
        },
        "title": {
            "type": "STRING",
            "description": "職稱或頭銜，如果看不出來，請填寫 N/A"
        },
        "company": {
            "type": "STRING",
            "description": "公司名稱，如果看不出來，請填寫 N/A"
        },
        "address": {
            "type": "STRING",
            "description": "公司或聯絡地址，如果看不出來，請填寫 N/A"
        },
        "phone": {
            "type": "STRING",
            "description": (
                "電話號碼，格式為 #886-0123-456-789,1234。"
                "沒有分機就忽略 ,1234。如果看不出來，請填寫 N/A"
            )
        },
        "email": {
            "type": "STRING",
            "description": "電子郵件信箱，如果看不出來，請填寫 N/A"
        }
    },
    "required": ["name", "title", "company", "address", "phone", "email"]
}


def generate_json_from_image(img: PIL.Image.Image, prompt: str) -> object:
    model = GenerativeModel(
        "gemini-3-flash-preview",
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": NAMECARD_SCHEMA
        },
    )
    img_part = Part.from_data(data=pil_to_bytes(img), mime_type="image/jpeg")
    response = model.generate_content([prompt, img_part], stream=False)
    return response
