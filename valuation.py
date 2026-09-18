# -*- coding: utf-8 -*-
"""Оценка ника: рыночная база x поправки признаков. Без сети.

Порядок расчёта (каждый шаг - отдельная функция):
  1. class_price      - медиана реальных продаж того же класса и длины;
  2. feature_modifier - произносимость, зеркальность;
  3. blend_similar    - для ников без слова смешиваем с медианой похожих
                        продаж (тот же префикс, длина, типы символов);
  4. blend_own_price  - если у ника есть своя цена на Fragment, тянемся к ней;
  5. не ниже цены создания; ранг и звёзды по порогам из config.
"""

import math
import statistics
from dataclasses import dataclass, field

import config
import features

CLASSES_FALLBACK = ("pronounce", "random")


@dataclass
class Result:
    name: str
    price_ton: float
    rank: int
    stars: int
    valuable: bool
    creation_ton: float
    pros: list = field(default_factory=list)
    cons: list = field(default_factory=list)
    similar: list = field(default_factory=list)       # [(name, price)] до 5 шт
    feats: object = None


def length_bucket(n):
    return min(n, 9)


def name_class(f):
    """Класс ника для таблицы медиан. Порядок важен: сильный признак первым."""
    if f.has_underscore:
        return "underscore"
    if f.pure_number:
        return "number"
    if f.repeat_pretty:
        return "repeat"
    if f.has_digits:
        return "digits_w" if f.word else "digits"
    if f.two_words:
        return "two_words"
    if f.word_kind:
        return f.word_kind
    return "random" if f.random_letters else "pronounce"


def class_price(f):
    """Медиана продаж класса; нет такой длины - ближайшая длина, потом случайные."""
    med = config.CALIBRATION["medians"]
    cls, L = name_class(f), length_bucket(f.length)
    for c in (cls,) + CLASSES_FALLBACK:
        for d in (0, 1, -1, 2, -2, 3):
            key = "%s:%d" % (c, L + d)
            if key in med:
                return med[key]
    return config.CALIBRATION["creation_ton"]


def feature_modifier(f):
    """Произносимость важна только для ников без слова: слово и так читается."""
    k = 1.0
    if not f.word and f.pronounce >= config.PRONOUNCE_GOOD:
        k *= config.MOD_PRONOUNCE_GOOD
    if not f.word and f.pronounce < config.PRONOUNCE_BAD:
        k *= config.MOD_PRONOUNCE_BAD
    if f.mirror and not f.repeat_pretty:
        k *= config.MOD_MIRROR
    return k


def similar_sales(f, sales):
    """Похожие продажи: сначала та же длина и типы символов, потом ближние длины."""
    others = [s for s in sales if s[0] != f.name]
    same = [s for s in others if len(s[0]) == f.length
            and features.char_classes(s[0]) == f.char_classes]
    rest = sorted((s for s in others if s not in same),
                  key=lambda s: (abs(len(s[0]) - f.length), s[1]))
    return sorted(same, key=lambda s: s[1]), rest


def geo_blend(a, b, weight_b):
    return math.exp((1 - weight_b) * math.log(max(a, 1)) + weight_b * math.log(max(b, 1)))


def blend_similar(price, f, same):
    if f.word or len(same) < config.SIMILAR_MIN_COUNT:
        return price
    return geo_blend(price, statistics.median(p for _, p in same), config.SIMILAR_WEIGHT)


def blend_own_price(price, own_price):
    if not own_price:
        return price
    return geo_blend(price, own_price, config.OWN_PRICE_WEIGHT)


def rank_of(price_ton):
    for i, bound in enumerate(config.RANK_BOUNDS):
        if price_ton <= bound:
            return i + 1
    return 10


def stars_of(f, confirmed):
    """Потенциал 1..5 из признаков спроса."""
    s = 1
    if f.word_kind in ("brand", "common_word"):
        s += 2
    elif f.word_kind or f.two_words or f.repeat_pretty or f.pure_number:
        s += 1
    if f.length <= 4:
        s += 1
    if confirmed:
        s += 1
    return max(1, min(5, s))


def explain(f, res, on_fragment, own_sales, same):
    """Преимущества и недостатки словами."""
    pros, cons = [], []
    kinds = {"brand": "🏷 Бренд или крипто-тематика — высокий спрос",
             "common_word": "📖 Настоящее английское слово",
             "dict_word": "📚 Словарное английское слово",
             "name": "👤 Популярное имя",
             "translit": "🇷🇺 Русское слово латиницей"}
    if f.two_words:
        pros.append("🧩 Состоит из двух слов: " + f.word)
    elif f.word_kind:
        pros.append(kinds[f.word_kind])
    elif f.word:
        pros.append("🔤 Содержит слово «%s»" % f.word)

    if f.length <= 4:
        pros.append("✂️ Всего 4 символа — премиальная длина")
    elif f.length == 5:
        pros.append("📏 5 символов — длина выше среднего")
    elif f.length >= 9:
        cons.append("📏 Длинный ник — спрос ниже")

    if f.repeat_pretty:
        pros.append("🔁 Красивый повтор символов")
    if f.mirror and not f.repeat_pretty:
        pros.append("🪞 Читается одинаково в обе стороны")
    if f.pure_number:
        pros.append("🔢 Чистое число")
    elif f.has_digits:
        cons.append("🔢 Цифры снижают спрос")
    if f.has_underscore:
        cons.append("➖ Подчёркивание снижает стоимость")

    if f.random_letters:
        cons.append("🔀 Случайный набор букв" + (" — стоимость не выше создания"
                                                if not res.valuable else ""))
    if not f.word and f.pronounce < config.PRONOUNCE_BAD:
        cons.append("🗣 Сложен в произношении")
    elif not f.word and f.pronounce >= config.PRONOUNCE_GOOD:
        pros.append("🗣 Легко произносится")

    if on_fragment:
        pros.append("✅ Есть на Fragment — спрос подтверждён рынком")
    else:
        cons.append("❓ Нет в базе Fragment — спрос не подтверждён рынком")
    if own_sales:
        pros.append("💸 Уже продавался на Fragment")
    elif f.word:
        pass    # продажи по префиксу - про другие слова, выводов по ним не делаем
    elif not same or statistics.median(p for _, p in same) <= res.creation_ton * 1.5:
        cons.append("📉 Нет подтверждённых продаж")
    else:
        pros.append("📈 Похожие ники продаются дороже создания")
    return pros, cons


def evaluate(name, sales, creation_ton=None, on_fragment=False, own_price=0.0,
             own_sales=0):
    """sales - [(ник, цена TON)] проданных по префиксу; own_price - своя цена на Fragment."""
    f = features.analyze(name)
    creation = creation_ton or config.CALIBRATION["creation_ton"]
    same, rest = similar_sales(f, sales)

    price = class_price(f) * feature_modifier(f)
    price = blend_similar(price, f, same)
    price = blend_own_price(price, own_price)
    price = max(price, creation)
    price = round(price) if price >= 20 else round(price, 1)

    confirmed = bool(own_sales) or (len(same) >= config.SIMILAR_MIN_COUNT and
                                    statistics.median(p for _, p in same) > creation * 3)
    res = Result(name=f.name, price_ton=price, rank=rank_of(price),
                 stars=stars_of(f, confirmed),
                 valuable=price > creation * config.VALUABLE_FACTOR,
                 creation_ton=creation, similar=(same + rest)[:5], feats=f)
    res.pros, res.cons = explain(f, res, on_fragment, own_sales, same)
    return res
