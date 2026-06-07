import os
import sys
import PIL.Image
import PIL.ImageDraw
from io import BytesIO

# 將 app 的上級目錄加入 path，以便導入 app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import gemini_utils, config, utils

def create_dummy_namecard_image() -> PIL.Image.Image:
    # 建立一個白色的名片背景
    img = PIL.Image.new("RGB", (600, 350), color="white")
    draw = PIL.ImageDraw.Draw(img)
    
    # 寫上名片資訊
    text = (
        "姓名：王大明 (David Wang)\n"
        "職稱：資深後端工程師\n"
        "公司：科技新創股份有限公司\n"
        "地址：台北市信義區信義路五段7號\n"
        "電話：#886-02-2345-6789,1234\n"
        "Email：david.wang@startup.com"
    )
    
    # 畫在圖片上
    draw.text((50, 50), text, fill="black")
    return img

def main():
    print("=== Testing Gemini Structured Outputs ===")
    
    # 檢查必要環境變數
    if not os.getenv("PROJECT_ID"):
        print("Error: PROJECT_ID environment variable is not set.")
        sys.exit(1)
        
    img = create_dummy_namecard_image()
    print("Dummy namecard image created.")
    
    print("Calling gemini_utils.generate_json_from_image with schema...")
    try:
        response = gemini_utils.generate_json_from_image(img, config.IMGAGE_PROMPT)
        print("API call successful. Raw response text:")
        print(response.text)
        
        print("\nParsing result using utils.parse_gemini_result_to_json...")
        card_obj = utils.parse_gemini_result_to_json(response.text)
        print(f"Parsed Card Object: {card_obj}")
        
        # 驗證欄位是否完全一致
        expected_keys = {"name", "title", "company", "address", "phone", "email"}
        actual_keys = set(k.lower() for k in card_obj.keys())
        
        missing = expected_keys - actual_keys
        if missing:
            print(f"❌ Verification Failed! Missing keys: {missing}")
            sys.exit(1)
        else:
            print("✅ Verification Successful! All expected keys are present in the output.")
            
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
