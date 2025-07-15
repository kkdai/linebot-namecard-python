import google.generativeai as genai
import PIL.Image


def generate_gemini_text_complete(prompt: list) -> object:
    """Gemini 文字生成，強制要求結構化 JSON 輸出"""
    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    response = model.generate_content(prompt)
    return response


def generate_json_from_image(img: PIL.Image.Image, prompt: str) -> object:
    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    response = model.generate_content([prompt, img], stream=True)
    response.resolve()
    return response
