from firebase_admin import db, storage
from . import config
from io import BytesIO
from datetime import timedelta, datetime
from collections import Counter


def get_all_cards(u_id: str) -> dict:
    """取得使用者所有名片資料"""
    try:
        ref = db.reference(f"{config.NAMECARD_PATH}/{u_id}")
        namecard_data = ref.get()
        return namecard_data or {}
    except Exception as e:
        print(f"Error fetching namecards: {e}")
        return {}


def add_namecard(namecard_obj: dict, u_id: str) -> str:
    """新增名片資料到 Firebase 並回傳 card_id"""
    try:
        # 加入建立時間戳記
        namecard_obj['created_at'] = datetime.now().isoformat()

        ref = db.reference(f"{config.NAMECARD_PATH}/{u_id}")
        new_card_ref = ref.push(namecard_obj)
        return new_card_ref.key  # 回傳新資料的唯一 ID
    except Exception as e:
        print(f"Error adding namecard: {e}")
        return None


def update_namecard_memo(card_id: str, u_id: str, memo: str) -> bool:
    """更新指定名片的備忘錄"""
    try:
        ref = db.reference(f"{config.NAMECARD_PATH}/{u_id}/{card_id}")
        ref.update({"memo": memo})
        return True
    except Exception as e:
        print(f"Error updating memo: {e}")
        return False


def remove_redundant_data(u_id: str) -> None:
    """移除重複 email 的名片資料"""
    try:
        ref = db.reference(f"{config.NAMECARD_PATH}/{u_id}")
        namecard_data = ref.get()
        if namecard_data:
            email_map = {}
            for key, value in namecard_data.items():
                email = value.get("email")
                if email:
                    if email in email_map:
                        ref.child(key).delete()
                    else:
                        email_map[email] = key
    except Exception as e:
        print(f"Error removing redundant data: {e}")


def check_if_card_exists(namecard_obj: dict, u_id: str) -> str:
    """檢查名片是否已存在 (以 email 為主鍵)，若存在則回傳 card_id"""
    try:
        email = namecard_obj.get("email")
        if not email:
            return None
        ref = db.reference(f"{config.NAMECARD_PATH}/{u_id}")
        namecard_data = ref.get()
        if namecard_data:
            for card_id, value in namecard_data.items():
                if value.get("email") == email:
                    return card_id  # 回傳已存在名片的 ID
        return None
    except Exception as e:
        print(f"Error checking if namecard exists: {e}")
        return None


def get_name_from_card(u_id: str, card_id: str) -> str:
    """從 Firebase 取得名片主人的名字"""
    try:
        ref = db.reference(f"{config.NAMECARD_PATH}/{u_id}/{card_id}")
        card_doc = ref.get()
        if not card_doc:
            return None
        return card_doc.get('name', '這位聯絡人')
    except Exception as e:
        print(f"Error getting name from card: {e}")
        return None


def get_card_by_id(u_id: str, card_id: str) -> dict:
    """用 card_id 取得名片"""
    try:
        ref = db.reference(f"{config.NAMECARD_PATH}/{u_id}/{card_id}")
        return ref.get()
    except Exception as e:
        print(f"Error getting card by id: {e}")
        return None


def update_namecard_field(
        u_id: str, card_id: str, field: str, value: str) -> bool:
    """更新指定名片的特定欄位"""
    try:
        ref = db.reference(f"{config.NAMECARD_PATH}/{u_id}/{card_id}")
        ref.update({field: value})
        return True
    except Exception as e:
        print(f"Error updating {field}: {e}")
        return False


def upload_qrcode_to_storage(
        image_bytes: BytesIO, user_id: str, card_id: str) -> str:
    """
    上傳 QR Code 圖片到 Firebase Storage 並回傳公開 URL

    Args:
        image_bytes: QR Code 圖片的 BytesIO 物件
        user_id: 使用者 ID
        card_id: 名片 ID

    Returns:
        圖片的公開 URL，若失敗則回傳 None
    """
    try:
        bucket = storage.bucket()
        blob_name = f"qrcodes/{user_id}/{card_id}.png"
        blob = bucket.blob(blob_name)

        # 上傳圖片
        image_bytes.seek(0)  # 重置指標到開頭
        blob.upload_from_file(image_bytes, content_type='image/png')

        # 設定為公開可讀取
        blob.make_public()

        # 回傳公開 URL
        return blob.public_url
    except Exception as e:
        print(f"Error uploading QR code to storage: {e}")
        return None


def get_namecard_statistics(u_id: str) -> dict:
    """
    取得名片統計資訊

    Returns:
        {
            "total": 總名片數,
            "this_month": 本月新增數量,
            "top_company": 最常聯絡公司名稱
        }
    """
    try:
        all_cards = get_all_cards(u_id)
        if not all_cards:
            return {
                "total": 0,
                "this_month": 0,
                "top_company": "無"
            }

        # 1. 計算總數
        total = len(all_cards)

        # 2. 計算本月新增
        now = datetime.now()
        this_month_count = 0

        for card in all_cards.values():
            created_at = card.get('created_at')
            if created_at:  # 只計算有時間戳的名片
                try:
                    created_date = datetime.fromisoformat(created_at)
                    if (created_date.year == now.year
                            and created_date.month == now.month):
                        this_month_count += 1
                except ValueError:
                    continue  # 忽略格式錯誤的時間戳

        # 3. 找出最常聯絡公司（名片數量最多的公司）
        companies = [
            card.get('company', '').strip()
            for card in all_cards.values()
            if card.get('company')
            and card.get('company') != 'N/A'
            and card.get('company').strip()
        ]

        if companies:
            company_counter = Counter(companies)
            top_company, count = company_counter.most_common(1)[0]
            top_company = f"{top_company} ({count}張)"
        else:
            top_company = "無"

        return {
            "total": total,
            "this_month": this_month_count,
            "top_company": top_company
        }

    except Exception as e:
        print(f"Error getting statistics: {e}")
        return {
            "total": 0,
            "this_month": 0,
            "top_company": "無"
        }
