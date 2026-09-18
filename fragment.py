# -*- coding: utf-8 -*-
"""Данные Fragment: статус ника, цены, история, похожие продажи.

Что делает сам сайт (DevTools):
  * страница ника - GET /username/<ник>; если ника на Fragment нет, отдаёт
    302 на /?query=<ник>;
  * поиск - GET /?query=<q>&filter=sold&sort=price_asc. Переходы внутри сайта
    идут тем же адресом с заголовком X-Aj-Referer, ответ - JSON {"h": html},
    это и есть их API. Подгрузка следующих страниц - POST /api?hash=...
    (hash живёт в ajInit на странице), но без cookie сессии отвечает
    "Bad request", поэтому берём первую страницу через Aj-JSON, а при сбое
    обычный HTML;
  * курс TON лежит в ajInit.state.tonRate - запасной источник курса.

Все запросы через один асинхронный ограничитель: не чаще 2 в секунду,
на 429 пауза растёт, ответы в кэше на FRAGMENT_CACHE_SEC.
"""

import asyncio
import html as htmllib
import json
import logging
import re
import time
from dataclasses import dataclass, field

import aiohttp

import config

log = logging.getLogger("fragment")
BASE = "https://fragment.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# статусы ника
ON_AUCTION = "auction"
FOR_SALE = "sale"
SOLD = "sold"
TAKEN = "taken"
ABSENT = "absent"          # на Fragment нет
UNKNOWN = "unknown"

LABELS = {"on auction": ON_AUCTION, "for sale": FOR_SALE, "available": FOR_SALE,
          "sold": SOLD, "taken": TAKEN}


class FragmentError(Exception):
    pass


@dataclass
class Sale:
    name: str
    price: float
    date: str = ""


@dataclass
class Page:
    name: str
    status: str
    price: float = 0.0          # цена продажи / текущая ставка / цена продажи без аукциона
    min_bid: float = 0.0
    history: list = field(default_factory=list)   # [Sale] от новых к старым
    ton_rate: float = 0.0


class Client:
    def __init__(self):
        self._session = None
        self._lock = asyncio.Lock()
        self._last = 0.0
        self._cache = {}

    async def close(self):
        if self._session:
            await self._session.close()

    async def _get(self, path, aj=False):
        key = (path, aj)
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < config.FRAGMENT_CACHE_SEC:
            return hit[1]
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": UA}, timeout=aiohttp.ClientTimeout(total=25))
        headers = {"X-Aj-Referer": BASE + "/", "X-Requested-With": "XMLHttpRequest",
                   "Accept": "application/json"} if aj else {}

        for attempt, pause in enumerate((0,) + config.FRAGMENT_BACKOFF):
            if pause:
                await asyncio.sleep(pause)
            async with self._lock:
                wait = config.FRAGMENT_MIN_GAP - (time.time() - self._last)
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last = time.time()
                try:
                    async with self._session.get(BASE + path, headers=headers,
                                                 allow_redirects=False) as r:
                        if r.status == 429 or r.status >= 500:
                            log.warning("%s -> %s, пауза", path, r.status)
                            continue
                        if r.status in (301, 302):
                            result = (r.status, r.headers.get("Location", ""))
                        else:
                            result = (r.status, await r.text())
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    log.warning("%s: %s", path, e)
                    continue
            self._cache[key] = (time.time(), result)
            return result
        raise FragmentError("Fragment не ответил: " + path)

    async def page(self, name):
        status, body = await self._get("/username/" + name)
        if status in (301, 302):
            return Page(name, ABSENT)
        if status != 200:
            raise FragmentError("HTTP %s" % status)
        return parse_page(name, body)

    async def number_page(self, digits):
        """Анонимный номер +888: /number/<цифры>, разметка как у ника."""
        status, body = await self._get("/number/" + digits)
        if status in (301, 302):
            return Page(digits, ABSENT)
        if status != 200:
            raise FragmentError("HTTP %s" % status)
        return parse_page(digits, body)

    async def similar_sales(self, query):
        """Проданные ники по префиксу, от дешёвых к дорогим."""
        path = "/?query=%s&filter=sold&sort=price_asc" % query
        try:
            status, body = await self._get(path, aj=True)
            body = json.loads(body)["h"]
        except (FragmentError, ValueError, KeyError, TypeError) as e:
            log.info("Aj-поиск не сработал (%s), берём HTML", e)
            status, body = await self._get(path)
        return parse_search(body)


def creation_cost(sales):
    """Цена создания - самая частая цена продажи ников без слова.

    Минимальная ставка аукциона не годится: у перепродаж она бывает 2 TON.
    А новые случайные ники массово уходят по одной цене (сейчас 10 TON) -
    её и берём из живой выдачи. Мало данных - мода по снимку продаж.
    """
    import features
    from collections import Counter
    prices = [s.price for s in sales
              if len(s.name) >= 5 and features.analyze(s.name).random_letters]
    if len(prices) >= config.CREATION_MIN_SAMPLES:
        return Counter(prices).most_common(1)[0][0]
    return config.CALIBRATION["creation_ton"]


def _num(s):
    s = htmllib.unescape(s).replace(",", "").strip()
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group()) if m else 0.0


def parse_page(name, html):
    m = re.search(r'tm-section-header-status[^"]*">([^<]+)<', html)
    label = m.group(1).strip().lower() if m else ""
    status = LABELS.get(label, UNKNOWN)
    page = Page(name, status)

    rate = re.search(r'"tonRate":([\d.]+)', html)
    page.ton_rate = float(rate.group(1)) if rate else 0.0

    # блок цены над описанием: Highest Bid / Minimum Bid / Sale Price / Sell Price
    box = html.split("tm-section-auction-info")[0]
    heads = [h.strip().lower() for h in re.findall(r"<th[^>]*>([^<]+)</th>", box)]
    vals = [_num(v) for v in re.findall(r'icon-ton">([^<]+)<', box)]
    for h, v in zip(heads, vals):
        if h in ("highest bid", "sale price", "sell price"):
            page.price = v
        elif h == "minimum bid":
            page.min_bid = v
    if not page.price and vals and status in (SOLD, FOR_SALE):
        page.price = vals[0]

    hist = html.split("Ownership History", 1)
    if len(hist) == 2:
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", hist[1], re.S):
            price = re.search(r'icon-ton">([^<]+)<', row)
            date = re.search(r'datetime="([^"]+)"', row)
            if price:
                page.history.append(Sale(name, _num(price.group(1)),
                                         date.group(1)[:10] if date else ""))
    return page


def parse_search(html):
    sales = []
    for row in re.findall(r'<tr class="tm-row-selectable">(.*?)</tr>', html, re.S):
        n = re.search(r'tm-value">@([a-z0-9_]+)<', row)
        p = re.search(r'icon-ton">([^<]+)<', row)
        d = re.search(r'datetime="([^"]+)"', row)
        if n and p and "Sold" in row:
            sales.append(Sale(n.group(1), _num(p.group(1)), d.group(1)[:10] if d else ""))
    return sales
