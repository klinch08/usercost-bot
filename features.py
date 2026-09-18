# -*- coding: utf-8 -*-
"""Признаки ника: что в нём есть, без всякой цены.

Каждое правило - отдельная функция. На выходе Features, по которому
valuation.py считает множители и списки преимуществ/недостатков.
"""

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
VOWELS = set("aeiouy")

# Бренды, крипта и тематика, которые на Fragment стабильно дорогие
BRANDS = set("""
ton btc eth usdt usdc sol bnb doge shib pepe notcoin not dogs trx xrp ada dot
crypto bitcoin ethereum wallet token nft dao defi web3 swap stake pool mint coin
binance bybit okx kucoin gate mexc htx tonkeeper tonapi fragment telegram durov
apple iphone google android tesla nike adidas gucci prada dior chanel bmw audi
mercedes porsche ferrari lambo rolex visa mastercard paypal amazon ebay netflix
spotify youtube tiktok instagram facebook meta twitter openai chatgpt gpt ai
bank casino bet poker slots lottery vip gold diamond luxury premium elite money
cash pay shop store market news game games play win sport football hotel travel
""".split())

# Русские слова латиницей: частые в нишах Telegram
TRANSLIT = set("""
dengi kot koshka sobaka mama papa privet poka lubov lyubov drug druzya zhizn mir
dom kvartira rabota vakansii novosti kino film muzika muzyka pesni igra igry
magazin skidki kupit prodat tovar tovary krasota moda zdorovie sport futbol
biznes kripta kriptovalyuta birzha investicii dohod zarabotok schastie son
devushka paren zhenshina muzhik vodka pivo eda recepty kuhnya avto mashina
moskva piter rossiya ukraina kazan sochi krym bratan bratva pacan poehali
""".split())


@lru_cache(maxsize=None)
def _words(fname):
    path = os.path.join(DATA, fname)
    with open(path, encoding="utf-8") as f:
        return frozenset(w.strip().lower() for w in f if w.strip())


@dataclass
class Features:
    name: str
    length: int
    word_kind: str = ""          # common_word / dict_word / name / brand / translit
    word: str = ""
    two_words: bool = False
    pronounce: float = 0.0       # 0..1
    has_digits: bool = False
    has_underscore: bool = False
    pure_number: bool = False
    repeat_pretty: bool = False
    mirror: bool = False
    random_letters: bool = False
    char_classes: str = ""
    notes: list = field(default_factory=list)


def char_classes(name):
    """Типы символов: l - буквы, d - цифры, u - подчёркивание."""
    return "".join(k for k, ok in (("l", re.search(r"[a-z]", name)),
                                    ("d", re.search(r"\d", name)),
                                    ("u", "_" in name)) if ok)


def word_kind(token):
    """Какое это слово: бренд важнее обычного, обычное важнее редкого."""
    if token in BRANDS:
        return "brand"
    if token in _words("words_common.txt"):
        return "common_word"
    if token in TRANSLIT:
        return "translit"
    if token in _words("names.txt"):
        return "name"
    # редкое словарное слово засчитываем только от 4 букв:
    # в полном словаре полно трёхбуквенного мусора
    if len(token) >= 4 and token in _words("words_all.txt"):
        return "dict_word"
    return ""


def split_two_words(name):
    """moneyrain -> (money, rain): два настоящих слова подряд."""
    best = None
    for i in range(3, len(name) - 2):
        a, b = name[:i], name[i:]
        ka, kb = word_kind(a), word_kind(b)
        if ka and kb and ka != "dict_word" and kb != "dict_word":
            best = (a, b)
    return best


def pronounceability(letters):
    """0..1: доля переходов гласная/согласная, штраф за 3+ согласных подряд."""
    if len(letters) < 2:
        return 0.0
    flips = sum((a in VOWELS) != (b in VOWELS) for a, b in zip(letters, letters[1:]))
    score = flips / (len(letters) - 1)
    clusters = re.findall(r"[^aeiouy]{3,}", letters)
    score -= 0.25 * sum(len(c) - 2 for c in clusters)
    if not any(c in VOWELS for c in letters):
        score = 0.0
    return max(0.0, min(1.0, score))


def is_repeat_pretty(name):
    """aaaa, 7777, abab, aabb - повторы, которые ценят коллекционеры."""
    if len(set(name)) == 1:
        return True
    if len(name) % 2 == 0 and name[: len(name) // 2] * 2 == name and len(set(name)) <= 2:
        return True
    return bool(re.fullmatch(r"(.)\1(.)\2", name))


def is_mirror(name):
    return len(name) >= 4 and name == name[::-1]


def analyze(name):
    name = name.lower().lstrip("@")
    f = Features(name=name, length=len(name), char_classes=char_classes(name))
    f.has_digits = bool(re.search(r"\d", name))
    f.has_underscore = "_" in name
    f.pure_number = name.isdigit()
    f.repeat_pretty = is_repeat_pretty(name)
    f.mirror = is_mirror(name)

    letters = re.sub(r"[^a-z]", "", name)
    f.pronounce = pronounceability(letters)

    kind = word_kind(name) if name.isalpha() else ""
    if kind:
        f.word_kind, f.word = kind, name
    elif name.isalpha():
        pair = split_two_words(name)
        if pair:
            f.two_words, f.word = True, " + ".join(pair)
            f.word_kind = word_kind(pair[0])
    else:
        # слово с цифрами или подчёркиванием: crypto_news, money77
        parts = [p for p in re.split(r"[\d_]+", name) if len(p) >= 3]
        for p in parts:
            k = word_kind(p)
            if k and k != "dict_word":
                f.word, f.notes = p, ["слово внутри: " + p]
                break

    f.random_letters = (not f.word and not f.pure_number and not f.repeat_pretty
                        and f.pronounce < 0.5)
    return f
