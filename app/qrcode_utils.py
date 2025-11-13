"""
QR Code generation utilities for namecard vCard export.
"""
import qrcode
from io import BytesIO
from typing import Dict, Optional


def generate_vcard_string(namecard_data: Dict[str, str]) -> str:
    """
    Generate vCard 3.0 format string from namecard data.

    Args:
        namecard_data: Dictionary containing namecard fields

    Returns:
        vCard formatted string
    """
    name = namecard_data.get('name', '')
    title = namecard_data.get('title', '')
    company = namecard_data.get('company', '')
    phone = namecard_data.get('phone', '')
    email = namecard_data.get('email', '')
    address = namecard_data.get('address', '')
    memo = namecard_data.get('memo', '')

    # Build vCard 3.0 format
    vcard_lines = [
        'BEGIN:VCARD',
        'VERSION:3.0',
        f'FN:{name}',
        f'N:{name};;;',  # Family Name; Given Name; Additional Names; Honorific Prefixes; Honorific Suffixes
    ]

    if company:
        vcard_lines.append(f'ORG:{company}')

    if title:
        vcard_lines.append(f'TITLE:{title}')

    if phone:
        # Clean phone number format for vCard
        clean_phone = phone.replace('-', '').replace(' ', '')
        vcard_lines.append(f'TEL;TYPE=WORK,VOICE:{clean_phone}')

    if email:
        vcard_lines.append(f'EMAIL;TYPE=WORK:{email}')

    if address:
        # vCard address format: PO Box;Extended Address;Street;City;Region;Postal Code;Country
        vcard_lines.append(f'ADR;TYPE=WORK:;;{address};;;;')

    if memo:
        # Escape special characters in memo
        escaped_memo = memo.replace('\n', '\\n').replace(',', '\\,').replace(';', '\\;')
        vcard_lines.append(f'NOTE:{escaped_memo}')

    vcard_lines.append('END:VCARD')

    return '\n'.join(vcard_lines)


def generate_vcard_qrcode(namecard_data: Dict[str, str],
                          box_size: int = 10,
                          border: int = 2) -> BytesIO:
    """
    Generate QR Code image containing vCard data.

    Args:
        namecard_data: Dictionary containing namecard fields
        box_size: Size of each box in pixels (default: 10)
        border: Border size in boxes (default: 2)

    Returns:
        BytesIO object containing PNG image data
    """
    # Generate vCard string
    vcard_string = generate_vcard_string(namecard_data)

    # Create QR Code instance
    qr = qrcode.QRCode(
        version=None,  # Auto-determine version based on data size
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=box_size,
        border=border,
    )

    # Add vCard data
    qr.add_data(vcard_string)
    qr.make(fit=True)

    # Generate image
    img = qr.make_image(fill_color="black", back_color="white")

    # Save to BytesIO
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)  # Reset pointer to beginning

    return img_bytes


def get_qrcode_usage_instruction(name: str) -> str:
    """
    Get user instruction message for using the QR Code.

    Args:
        name: Name of the person on the namecard

    Returns:
        Instruction message string
    """
    return f"""已為「{name}」生成聯絡人 QR Code！

📱 使用方式：
1. 用手機相機 App 掃描上方的 QR Code
2. 系統會自動識別聯絡人資訊
3. 點擊「加入聯絡人」即可匯入

✅ 支援 iPhone 和 Android 所有智慧型手機"""
