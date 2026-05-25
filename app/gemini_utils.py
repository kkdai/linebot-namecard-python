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


def generate_json_from_image(img: PIL.Image.Image, prompt: str) -> object:
    model = GenerativeModel(
        "gemini-3-flash-preview",
        generation_config={"response_mime_type": "application/json"},
    )
    img_part = Part.from_data(data=pil_to_bytes(img), mime_type="image/jpeg")
    response = model.generate_content([prompt, img_part], stream=False)
    return response
