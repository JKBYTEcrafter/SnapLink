"""
Social preview card generator.
Generates a styled PNG card for a short URL using Pillow.
"""
import io
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def generate_preview_card(short_url: str, long_url: str, click_count: int = 0) -> bytes:
    """
    Generate a social preview card PNG for a short URL.

    Returns PNG bytes.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import qrcode
        import qrcode.image.pil
    except ImportError as e:
        logger.error("Pillow or qrcode not available: %s", e)
        raise RuntimeError("Preview generation requires Pillow and qrcode packages.")

    # Card dimensions
    WIDTH, HEIGHT = 900, 470
    PADDING = 48

    # Color palette — dark glassmorphism
    BG_DARK = (10, 10, 20)
    CARD_BG = (18, 18, 35)
    ACCENT = (139, 92, 246)        # purple
    ACCENT2 = (59, 130, 246)       # blue
    TEXT_PRIMARY = (248, 250, 252)
    TEXT_SECONDARY = (148, 163, 184)
    BORDER = (55, 65, 81)
    GREEN = (34, 197, 94)

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Background gradient simulation via horizontal bands
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(BG_DARK[0] + (CARD_BG[0] - BG_DARK[0]) * ratio)
        g = int(BG_DARK[1] + (CARD_BG[1] - BG_DARK[1]) * ratio)
        b = int(BG_DARK[2] + (CARD_BG[2] - BG_DARK[2]) * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Accent glow blob — top-left purple
    for radius in range(180, 0, -10):
        alpha = int(255 * (1 - radius / 180) * 0.12)
        color = (ACCENT[0], ACCENT[1], ACCENT[2])
        draw.ellipse(
            [-radius // 2, -radius // 2, radius, radius],
            fill=color,
        )

    # Card border rectangle
    draw.rounded_rectangle(
        [PADDING - 12, PADDING - 12, WIDTH - PADDING + 12, HEIGHT - PADDING + 12],
        radius=20,
        outline=BORDER,
        width=1,
    )

    # Accent bar on the left
    draw.rounded_rectangle(
        [PADDING - 12, PADDING - 12, PADDING - 4, HEIGHT - PADDING + 12],
        radius=6,
        fill=ACCENT,
    )

    # Load fonts — use default if custom unavailable
    def _font(size: int):
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            try:
                return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
            except Exception:
                return ImageFont.load_default()

    font_brand = _font(22)
    font_title = _font(38)
    font_url = _font(18)
    font_small = _font(15)

    # Brand label — top left
    draw.text((PADDING + 12, PADDING + 4), "⚡ SnapLink", font=font_brand, fill=ACCENT)

    # Short URL (big, highlighted)
    short_display = short_url.replace("http://", "").replace("https://", "")
    draw.text((PADDING + 12, PADDING + 48), short_display, font=font_title, fill=TEXT_PRIMARY)

    # Separator line
    sep_y = PADDING + 110
    draw.line([(PADDING + 12, sep_y), (WIDTH - PADDING - 12, sep_y)], fill=BORDER, width=1)

    # Long URL (truncated)
    long_display = long_url
    if len(long_display) > 70:
        long_display = long_display[:67] + "..."
    draw.text((PADDING + 12, sep_y + 18), "→ " + long_display, font=font_url, fill=TEXT_SECONDARY)

    # Stats row
    stats_y = sep_y + 60
    draw.text((PADDING + 12, stats_y), f"👆 {click_count:,} clicks", font=font_small, fill=TEXT_SECONDARY)

    # Domain badge
    try:
        domain = urlparse(long_url).netloc or long_url[:30]
    except Exception:
        domain = ""
    if domain:
        badge_x = PADDING + 12
        badge_y = stats_y + 36
        badge_w = len(domain) * 8 + 24
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + badge_w, badge_y + 28],
            radius=8,
            fill=(30, 30, 60),
            outline=BORDER,
        )
        draw.text((badge_x + 10, badge_y + 6), domain, font=font_small, fill=ACCENT2)

    # Generate QR code (small)
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=2,
        )
        qr.add_data(short_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="white", back_color=(18, 18, 35))
        qr_pil = qr_img.convert("RGB")
        qr_size = 160
        qr_pil = qr_pil.resize((qr_size, qr_size), Image.LANCZOS)
        qr_x = WIDTH - PADDING - qr_size - 12
        qr_y = PADDING + 30
        # QR border
        draw.rounded_rectangle(
            [qr_x - 8, qr_y - 8, qr_x + qr_size + 8, qr_y + qr_size + 8],
            radius=12,
            fill=(24, 24, 48),
            outline=ACCENT,
        )
        img.paste(qr_pil, (qr_x, qr_y))
    except Exception as e:
        logger.warning("QR embed failed in preview: %s", e)

    # "Active" badge
    badge_text = "ACTIVE"
    badge_color = GREEN
    bx = WIDTH - PADDING - 12 - 80
    by = HEIGHT - PADDING - 8
    draw.rounded_rectangle([bx, by, bx + 80, by + 26], radius=8, fill=(0, 40, 20))
    draw.text((bx + 18, by + 5), badge_text, font=font_small, fill=badge_color)

    # Footer note
    draw.text(
        (PADDING + 12, HEIGHT - PADDING - 4),
        "Generated by SnapLink · snaplink.io",
        font=font_small,
        fill=(60, 70, 90),
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
