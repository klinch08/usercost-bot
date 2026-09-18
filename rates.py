# -*- coding: utf-8 -*-
"""Курс TON -> USD. CoinGecko, запасной Binance, кэш 5 минут."""

import logging
import time

import aiohttp

import config

log = logging.getLogger("rates")
_cache = (0.0, 0.0)

SOURCES = (
    ("https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd",
     lambda j: j["the-open-network"]["usd"]),
    ("https://api.binance.com/api/v3/ticker/price?symbol=TONUSDT",
     lambda j: j["price"]),
)


_rub_cache = (0.0, 0.0)


async def ton_rub():
    """Курс TON -> RUB с CoinGecko или 0, если не ответил."""
    global _rub_cache
    if time.time() - _rub_cache[0] < config.RATE_CACHE_SEC and _rub_cache[1]:
        return _rub_cache[1]
    url = "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=rub"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
            async with s.get(url) as r:
                rate = float((await r.json(content_type=None))["the-open-network"]["rub"])
        if rate > 0:
            _rub_cache = (time.time(), rate)
    except Exception as e:
        log.warning("курс рубля: %s", e)
    return _rub_cache[1]


async def ton_usd():
    """Курс или 0, если все источники молчат (тогда доллары не показываем)."""
    global _cache
    if time.time() - _cache[0] < config.RATE_CACHE_SEC and _cache[1]:
        return _cache[1]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
        for url, pick in SOURCES:
            try:
                async with s.get(url) as r:
                    rate = float(pick(await r.json(content_type=None)))
                if rate > 0:
                    _cache = (time.time(), rate)
                    return rate
            except Exception as e:
                log.warning("курс %s: %s", url.split("/")[2], e)
    return _cache[1]
