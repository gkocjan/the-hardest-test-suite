"""Renders the "camera frame" for a detection — the evidence in the HTML report.

The frame shows what the system SAW (read plate, seen color), not the ground
truth, so a failing test comes with a picture where the mistake is visible.
Pure Pillow, deterministic, no ML anywhere near.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 640, 360

COLORS = {
    "red": (188, 62, 53),
    "blue": (58, 94, 165),
    "navy": (28, 44, 82),
    "black": (28, 28, 30),
    "white": (228, 228, 224),
    "silver": (176, 180, 186),
    "green": (58, 122, 75),
    "yellow": (214, 178, 54),
}


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("DejaVuSansMono.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_car(draw: ImageDraw.ImageDraw, x: int, y: int, body: tuple) -> None:
    draw.rounded_rectangle([x, y + 40, x + 300, y + 120], radius=18, fill=body)
    draw.rounded_rectangle([x + 60, y, x + 240, y + 60], radius=14, fill=body)
    window = (168, 194, 214)
    draw.rounded_rectangle([x + 76, y + 10, x + 150, y + 52], radius=6, fill=window)
    draw.rounded_rectangle([x + 162, y + 10, x + 228, y + 52], radius=6, fill=window)
    for wx in (x + 60, x + 220):
        draw.ellipse([wx, y + 96, wx + 56, y + 152], fill=(18, 18, 20))
        draw.ellipse([wx + 14, y + 110, wx + 42, y + 138], fill=(90, 92, 96))


def _draw_rickshaw(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.rounded_rectangle([x + 40, y, x + 240, y + 90], radius=30, fill=(178, 122, 48))
    draw.rectangle([x + 40, y + 46, x + 240, y + 90], fill=(120, 82, 34))
    for wx in (x + 20, x + 130, x + 226):
        draw.ellipse([wx, y + 86, wx + 54, y + 140], outline=(60, 60, 64), width=6)


def _plate_area(draw, x, y, text: str, ghost: bool, font) -> None:
    if ghost:  # a newspaper tucked behind the vehicle, "read" as a plate
        draw.rectangle([x, y, x + 150, y + 46], fill=(226, 220, 202))
        for line_y in range(y + 26, y + 44, 5):
            draw.line([x + 8, line_y, x + 142, line_y], fill=(148, 142, 128), width=2)
        draw.text((x + 10, y + 5), text, font=font, fill=(60, 56, 48))
    else:
        draw.rectangle([x, y, x + 150, y + 40], fill=(238, 238, 234))
        draw.rectangle([x, y, x + 150, y + 40], outline=(40, 40, 44), width=3)
        draw.text((x + 12, y + 7), text, font=font, fill=(24, 24, 28))


def render_frame(
    path: Path,
    lot_name: str,
    camera: str,
    frame_time_ms: int,
    plate_read: str,
    color_seen: str,
    vehicle_type: str = "car",
    ghost: bool = False,
) -> Path:
    image = Image.new("RGB", (WIDTH, HEIGHT), (44, 47, 52))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, HEIGHT - 60, WIDTH, HEIGHT], fill=(52, 56, 62))  # roadway

    x = 90 + (frame_time_ms // 7) % 120  # position varies with time, deterministic
    if vehicle_type == "rickshaw":
        _draw_rickshaw(draw, x, 130)
    else:
        _draw_car(draw, x, 110, COLORS.get(color_seen, (120, 120, 124)))
    _plate_area(draw, x + 84, 236, plate_read or "?", ghost, _font(24))

    header = f"{lot_name} · {camera} · t+{frame_time_ms / 1000:.3f}s"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    draw.rectangle([0, 0, WIDTH, 30], fill=(20, 21, 24))
    draw.text((10, 6), header, font=_font(16), fill=(210, 210, 205))
    draw.text((WIDTH - 172, 6), stamp, font=_font(14), fill=(140, 142, 146))
    draw.text((10, HEIGHT - 24), "REC ●", font=_font(14), fill=(196, 84, 77))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path
