from firebase_admin import db
from . import config


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
