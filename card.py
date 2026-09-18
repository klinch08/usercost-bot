# -*- coding: utf-8 -*-
"""Карточка 1080x1080: ник, ранг, доллар, звёзды, водяной знак.

Иконки рисуются векторно, поэтому шрифту эмодзи не нужны. Шрифты с
кириллицей лежат в fonts/ (Unbounded, Manrope - OFL).
"""

import math
import os
from datetime import date

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config

S = 1080
FONTS = os.path.join(config.ROOT, "fonts")
BG_TOP, BG_BOTTOM = (10, 13, 24), (22, 27, 46)
MUTED = (120, 132, 165)
TEXT = (238, 242, 255)
GOLD = (255, 196, 64)
GREEN = (70, 214, 140)
RED = (255, 86, 96)
EMPTY = (58, 66, 96)


def _font(name, size, weight):
    f = ImageFont.truetype(os.path.join(FONTS, name), size)
    try:
        f.set_variation_by_axes([weight])
    except (OSError, AttributeError):
        pass
    return f


def _accent(rank):
    # от холодного серо-синего к золоту
    t = (rank - 1) / 9
    cold, hot = (92, 118, 190), GOLD
    return tuple(round(c + (h - c) * t) for c, h in zip(cold, hot))


def _star(cx, cy, r):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def render(name, rank, stars, valuable, bot_username):
    img = Image.new("RGB", (S, S))
    d = ImageDraw.Draw(img)
    for y in range(S):
        t = y / S
        d.line([(0, y), (S, y)], fill=tuple(round(a + (b - a) * t)
                                            for a, b in zip(BG_TOP, BG_BOTTOM)))
    accent = _accent(rank)

    # мягкое свечение за ником
    glow = Image.new("L", (S, S), 0)
    ImageDraw.Draw(glow).ellipse((190, 250, 890, 650), fill=70 + rank * 8)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img.paste(Image.new("RGB", (S, S), accent), (0, 0), glow)
    d = ImageDraw.Draw(img)

    d.rounded_rectangle((34, 34, S - 34, S - 34), radius=72, outline=(46, 55, 88), width=4)

    d.text((96, 104), config.BRAND, font=_font("Unbounded.ttf", 30, 700), fill=MUTED)

    badge = "RANK %d/10" % rank
    bf = _font("Unbounded.ttf", 34, 800)
    w = d.textlength(badge, font=bf)
    d.rounded_rectangle((S - 96 - w - 56, 84, S - 96, 156), radius=36, fill=accent)
    d.text((S - 96 - w - 28, 120), badge, font=bf, fill=BG_TOP, anchor="lm")

    nick = "@" + name
    size = 150
    while size > 40:
        nf = _font("Unbounded.ttf", size, 800)
        if d.textlength(nick, font=nf) <= 880:
            break
        size -= 6
    d.text((S // 2, 430), nick, font=nf, fill=TEXT, anchor="mm")

    # доллар в круге, перечёркнут, если ценности нет
    cx, cy, r = S // 2, 640, 78
    color = GREEN if valuable else MUTED
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=10)
    d.text((cx, cy + 4), "$", font=_font("Unbounded.ttf", 96, 800), fill=color, anchor="mm")
    if not valuable:
        k = r * 0.78
        d.line((cx - k, cy + k, cx + k, cy - k), fill=RED, width=14)

    gap, sr = 118, 44
    x0 = S // 2 - gap * 2
    for i in range(5):
        pts = _star(x0 + gap * i, 820, sr)
        if i < stars:
            d.polygon(pts, fill=GOLD)
        else:
            d.polygon(pts, outline=EMPTY, width=5)

    wm = "@" + bot_username
    d.text((S - 96, S - 92), wm, font=_font("Manrope.ttf", 34, 700), fill=MUTED, anchor="rs")
    return img


def cached(name, rank, stars, valuable, bot_username):
    """Путь к PNG; кэш по нику, дате и итогу оценки."""
    os.makedirs(config.CARDS_DIR, exist_ok=True)
    path = os.path.join(config.CARDS_DIR, "%s_%s_%d%d%d.png"
                        % (name, date.today().isoformat(), rank, stars, int(valuable)))
    if not os.path.exists(path):
        render(name, rank, stars, valuable, bot_username).save(path, optimize=True)
    return path
