"""Procedural editorial placeholder photos + per-supplier degraded variants.

No stock photos are shipped: every base image is drawn here from a seeded RNG, so the
repo stays licence-clean. Variants (crop, resize, JPEG quality, watermark, colour shift)
give the pHash dedup real work to do.
"""
from __future__ import annotations

import colorsys
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

TAGS = ["exterior", "exterior", "lobby", "pool", "room", "room", "room", "bathroom", "restaurant", "view",
        "room", "pool", "lobby", "exterior", "restaurant", "room"]
W, H = 720, 480


def _hsl(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h % 1.0, l, s)
    return int(r * 255), int(g * 255), int(b * 255)


def _gradient(img: Image.Image, top, bottom):
    d = ImageDraw.Draw(img)
    for y in range(img.height):
        t = y / max(1, img.height - 1)
        d.line([(0, y), (img.width, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))


def _exterior(rng, img):
    hue = rng.random()
    _gradient(img, _hsl(hue, 0.45, 0.78), _hsl(hue + 0.08, 0.55, 0.92))
    d = ImageDraw.Draw(img)
    sx, sy, sr = rng.randint(80, W - 80), rng.randint(40, 160), rng.randint(25, 55)
    d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=_hsl(0.1, 0.8, 0.75))
    horizon = rng.randint(300, 380)
    d.rectangle([0, horizon, W, H], fill=_hsl(0.53 + rng.random() * 0.05, 0.45, 0.45))
    for i in range(0, W, 6):
        d.line([(i, horizon + rng.randint(4, 90)), (i + 4, horizon + rng.randint(4, 90))], fill=_hsl(0.53, 0.4, 0.62))
    x = rng.randint(-20, 40)
    while x < W:
        bw, bh = rng.randint(40, 110), rng.randint(120, 320)
        col = _hsl(rng.random() * 0.15 + 0.55, 0.12, rng.uniform(0.25, 0.55))
        top = horizon - bh
        if rng.random() < 0.35:
            d.polygon([(x, horizon), (x + bw // 2, top - rng.randint(20, 80)), (x + bw, horizon)], fill=col)
        else:
            d.rectangle([x, top, x + bw, horizon], fill=col)
            for wy in range(top + 8, horizon - 8, rng.choice([10, 12, 14])):
                for wx in range(x + 5, x + bw - 5, rng.choice([8, 10, 12])):
                    if rng.random() < 0.6:
                        d.rectangle([wx, wy, wx + 3, wy + 5], fill=_hsl(0.12, 0.6, rng.uniform(0.6, 0.9)))
        x += bw + rng.randint(4, 30)


def _interior(rng, img, kind):
    hue = rng.choice([0.07, 0.09, 0.11, 0.55, 0.08, 0.95])
    _gradient(img, _hsl(hue, 0.25, 0.86), _hsl(hue, 0.3, 0.62))
    d = ImageDraw.Draw(img)
    floor = rng.randint(300, 360)
    d.rectangle([0, floor, W, H], fill=_hsl(hue + 0.02, 0.3, 0.45))
    for i in range(-W, 2 * W, rng.choice([40, 60, 80])):
        d.line([(W // 2, floor), (i, H)], fill=_hsl(hue, 0.25, 0.38), width=1)
    if kind == "room":
        wx = rng.randint(40, 380)
        d.rectangle([wx, 70, wx + 260, 260], fill=_hsl(0.56, 0.5, 0.75))
        d.rectangle([wx, 190, wx + 260, 260], fill=_hsl(0.55, 0.55, 0.5))
        bx = rng.randint(120, 360)
        d.rectangle([bx, floor - 70, bx + 300, floor + 40], fill=_hsl(0.1, 0.1, 0.95))
        d.rectangle([bx, floor - 120, bx + 300, floor - 70], fill=_hsl(hue, 0.35, 0.35))
        for p in range(3):
            px = bx + 20 + p * 90
            d.ellipse([px, floor - 95, px + 70, floor - 60], fill=_hsl(0.1, 0.05, 0.98))
        lx = rng.randint(20, 100)
        d.polygon([(lx, 200), (lx + 40, 200), (lx + 30, 160), (lx + 10, 160)], fill=_hsl(0.12, 0.6, 0.8))
    elif kind == "bathroom":
        for ty in range(0, floor, 30):
            for tx in range(0, W, 30):
                d.rectangle([tx + 1, ty + 1, tx + 29, ty + 29], outline=_hsl(hue, 0.1, 0.75))
        tx = rng.randint(80, 360)
        d.ellipse([tx, floor - 60, tx + 300, floor + 50], fill=_hsl(0.1, 0.05, 0.97))
        d.rectangle([rng.randint(20, 600), 60, rng.randint(620, 700), 170], fill=_hsl(0.55, 0.2, 0.82))
    elif kind == "lobby":
        for c in range(rng.randint(3, 6)):
            cx = rng.randint(30, W - 60)
            d.rectangle([cx, 40, cx + 26, floor], fill=_hsl(hue, 0.2, 0.92))
        for c in range(rng.randint(2, 4)):
            cx, cy = rng.randint(100, W - 100), rng.randint(40, 120)
            d.ellipse([cx - 30, cy - 15, cx + 30, cy + 15], fill=_hsl(0.12, 0.7, 0.8))
        d.rectangle([rng.randint(150, 300), floor - 50, rng.randint(400, 560), floor], fill=_hsl(hue, 0.4, 0.3))
    else:  # restaurant
        for t in range(rng.randint(5, 9)):
            cx, cy = rng.randint(40, W - 40), rng.randint(floor - 20, H - 30)
            r = rng.randint(22, 40)
            d.ellipse([cx - r, cy - r // 2, cx + r, cy + r // 2], fill=_hsl(0.1, 0.05, 0.96))
            d.ellipse([cx - 6, cy - 6, cx + 6, cy + 2], fill=_hsl(rng.random(), 0.5, 0.5))
        for c in range(rng.randint(3, 7)):
            cx = rng.randint(30, W - 30)
            d.line([(cx, 0), (cx, rng.randint(40, 110))], fill=_hsl(0.1, 0.2, 0.3), width=2)
            d.ellipse([cx - 10, 100, cx + 10, 120], fill=_hsl(0.12, 0.8, 0.75))


def _pool(rng, img):
    _gradient(img, _hsl(0.55, 0.5, 0.82), _hsl(0.55, 0.4, 0.9))
    d = ImageDraw.Draw(img)
    top = rng.randint(180, 260)
    d.rectangle([0, top, W, H], fill=_hsl(0.5, 0.6, 0.52))
    for i in range(140):
        x, y = rng.randint(0, W), rng.randint(top, H)
        d.arc([x - 30, y - 6, x + 30, y + 6], 200, 340, fill=_hsl(0.5, 0.6, 0.75), width=2)
    for i in range(rng.randint(4, 8)):
        x = rng.randint(0, W - 80)
        d.rectangle([x, top - 18, x + 70, top - 6], fill=_hsl(0.1, 0.1, 0.96))
    for i in range(rng.randint(2, 4)):
        px = rng.randint(30, W - 30)
        d.line([(px, top), (px + rng.randint(-20, 20), top - 150)], fill=_hsl(0.08, 0.4, 0.3), width=6)
        for a in range(6):
            d.ellipse([px - 60 + a * 18, top - 175 + rng.randint(-10, 10), px - 20 + a * 18, top - 145], fill=_hsl(0.3, 0.45, 0.35))


def _view(rng, img):
    hue = rng.choice([0.04, 0.06, 0.6, 0.62])
    _gradient(img, _hsl(hue, 0.6, 0.7), _hsl(hue + 0.05, 0.5, 0.88))
    d = ImageDraw.Draw(img)
    for layer in range(3):
        base = 260 + layer * 50
        pts = [(0, H)]
        x = 0
        while x <= W:
            pts.append((x, base - rng.randint(0, 120 - layer * 30)))
            x += rng.randint(20, 60)
        pts.append((W, H))
        d.polygon(pts, fill=_hsl(0.6, 0.15, 0.35 + layer * 0.12))


def make_base_image(seed: str, tag: str) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGB", (W, H))
    if tag == "exterior":
        _exterior(rng, img)
    elif tag == "pool":
        _pool(rng, img)
    elif tag == "view":
        _view(rng, img)
    else:
        _interior(rng, img, tag)
    img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.4, 1.1)))
    return img


def make_variant(img: Image.Image, rng: random.Random, watermark: str) -> tuple[Image.Image, int]:
    w, h = img.size
    crop = rng.uniform(0.05, 0.15)
    dx, dy = int(w * crop * rng.random()), int(h * crop * rng.random())
    v = img.crop((dx, dy, w - int(w * crop) + dx, h - int(h * crop) + dy))
    scale = rng.uniform(0.55, 1.0)
    v = v.resize((max(200, int(v.width * scale)), max(130, int(v.height * scale))), Image.LANCZOS)
    v = ImageEnhance.Color(v).enhance(rng.uniform(0.85, 1.15))
    v = ImageEnhance.Brightness(v).enhance(rng.uniform(0.92, 1.08))
    d = ImageDraw.Draw(v)
    try:
        font = ImageFont.load_default()
    except Exception:  # pragma: no cover
        font = None
    d.text((v.width - 8 - 6 * len(watermark), v.height - 16), watermark, fill=(255, 255, 255), font=font)
    return v, rng.randint(60, 90)


def save_jpeg(img: Image.Image, path: Path, quality: int = 85) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=quality, optimize=True)
