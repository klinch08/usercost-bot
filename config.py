# -*- coding: utf-8 -*-
"""Настройки бота и все пороги оценки в одном месте.

Секреты только из окружения: BOT_TOKEN, TG_SESSION, DATABASE_URL.
"""

import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
TG_SESSION = os.environ.get("TG_SESSION", "").strip()
# postgres://... на хостинге; без неё локальный SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH = os.environ.get("SQLITE_PATH", os.path.join(ROOT, "usercost.db"))
CARDS_DIR = os.path.join(ROOT, "cards")

TG_API_ID = int(os.environ.get("TG_API_ID", "33152316"))
TG_API_HASH = os.environ.get("TG_API_HASH", "0f4ceed1ef9092455948e984fedca172")

BRAND = "USERCOST"                 # подпись на карточке

# --- источники -------------------------------------------------------------
FRAGMENT_CACHE_SEC = 15 * 60
FRAGMENT_MIN_GAP = 0.5             # не больше двух запросов в секунду
FRAGMENT_BACKOFF = (5, 15, 45, 120)
RATE_CACHE_SEC = 5 * 60
CHECK_USERNAME_GAP = 1.0           # CheckUsername не чаще раза в секунду
WATCH_EVERY_MIN = int(os.environ.get("WATCH_EVERY_MIN", "20"))

# Цена создания = самая частая цена продажи случайных ников на Fragment
# (по живой выдаче поиска). Если выборка меньше CREATION_MIN_SAMPLES -
# та же мода по снимку продаж, посчитанная calibrate.py.
CREATION_MIN_SAMPLES = 3

# --- оценка ----------------------------------------------------------------
# Медианы продаж по (класс ника, длина) - генерирует calibrate.py
with open(os.path.join(ROOT, "data", "calibration.json"), encoding="utf-8") as _f:
    CALIBRATION = json.load(_f)

# Границы частотности английских слов (место в списке 10 000 частых слов):
# до 1000 - common_top, до 3000 - common_mid, дальше - common_low
WORD_RANK_TIERS = (1000, 3000)

# Поправки поверх медианы класса
PRONOUNCE_GOOD = 0.7        # произносимость выше - плюс
PRONOUNCE_BAD = 0.4         # ниже - минус
MOD_PRONOUNCE_GOOD = 1.3
MOD_PRONOUNCE_BAD = 0.8
MOD_MIRROR = 1.5

# вес похожих продаж (тот же префикс, длина и типы символов) для ников без слова:
# у слова продажи по префиксу про другие слова и ничего не говорят
SIMILAR_WEIGHT = 0.7        # подобрано перебором на 27 тыс. продаж (evaluate_model.py)
SIMILAR_MIN_COUNT = 3
# вес собственной цены ника на Fragment (последняя продажа, ставка, цена продажи)
OWN_PRICE_WEIGHT = 0.7

# Ранг по оценке в TON: верхние границы рангов 1..9, выше - 10.
# 1 = не дороже создания (10 TON), 10 = топ Fragment (слова и бренды из 4-5 букв).
RANK_BOUNDS = [15, 40, 120, 400, 1200, 4000, 15000, 50000, 200000]
# «представляет ценность», если оценка выше цены создания во столько раз
VALUABLE_FACTOR = 1.5
