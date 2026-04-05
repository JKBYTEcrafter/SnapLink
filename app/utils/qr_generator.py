"""
QR code generation utilities.
"""
import io

import qrcode
from qrcode.image.pil import PilImage


def generate_qr_bytes(url: str, box_size: int = 10, border: int = 4) -> bytes:
    """
    Generate a PNG QR code image for the given URL.

    Args:
        url: The URL to encode in the QR code.
        box_size: Pixel size of each QR box (default: 10).
        border: Border thickness in boxes (default: 4, minimum per spec).

    Returns:
        Raw PNG bytes of the QR code image.
    """
    qr = qrcode.QRCode(
        version=None,               # auto-determine version
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img: PilImage = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.read()
