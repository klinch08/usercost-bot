# -*- coding: utf-8 -*-
"""Сбор всех данных по нику и оценка. Общий для ответа, inline и отслеживания."""

import asyncio
import logging
from dataclasses import dataclass, field

import fragment
import rates
import tginfo
import valuation

log = logging.getLogger("service")


@dataclass
class Report:
    name: str
    result: valuation.Result
    page: object = None               # fragment.Page или None, если Fragment недоступен
    rate: float = 0.0                 # один курс на всё сообщение
    rub: float = 0.0                  # курс TON -> RUB
    errors: list = field(default_factory=list)
    tg: dict = None                   # флаги Telegram; None - проверка недоступна

    def state(self):
        """Снимок для отслеживания: что сравниваем между проверками."""
        p = self.page
        return {"status": p.status if p else None, "price": p.price if p else None,
                "sales": len(p.history) if p else None}


class Service:
    def __init__(self):
        self.fragment = fragment.Client()
        self.tg = tginfo.TgInfo()

    async def close(self):
        await self.fragment.close()

    async def report(self, name):
        name = name.lower()
        errors = []

        async def safe(coro, what):
            try:
                return await coro
            except Exception as e:
                log.error("%s для %s: %s: %s", what, name, type(e).__name__, e)
                errors.append(what)
                return None

        page, sales, rate, rub, tg = await asyncio.gather(
            safe(self.fragment.page(name), "fragment"),
            safe(self.fragment.similar_sales(name[:3]), "fragment_search"),
            safe(rates.ton_usd(), "rate"),
            safe(rates.ton_rub(), "rub"),
            self.tg.username(name))

        if not rate and page and page.ton_rate:
            rate = page.ton_rate          # курс со страницы Fragment как запасной
        if not rub and rate:
            rub = rate * (await rates.usd_rub())
        sales = sales or []
        own_price = 0.0
        if page:
            own_price = page.price or (page.history[0].price if page.history else 0.0)
        res = valuation.evaluate(
            name, [(s.name, s.price) for s in sales],
            creation_ton=fragment.creation_cost(sales) if sales else None,
            # «Taken» Fragment показывает для любого занятого ника - это не рынок
            on_fragment=bool(page) and (page.status in (fragment.ON_AUCTION, fragment.FOR_SALE,
                                                        fragment.SOLD) or bool(page.history)),
            own_price=own_price,
            # первая страница истории бывает из одних переводов, а сама продажа
            # за «Show more» - статус Sold уже значит, что продажа была
            own_sales=(len(page.history) or int(page.status == fragment.SOLD)) if page else 0)
        return Report(name, res, page, rate or 0.0, rub or 0.0, errors, tg)


@dataclass
class NumberReport:
    digits: str
    page: object = None
    rate: float = 0.0
    rub: float = 0.0
    tg: dict = None


async def number_report(svc, digits):
    async def safe(coro, what):
        try:
            return await coro
        except Exception as e:
            log.error("%s для +%s: %s: %s", what, digits, type(e).__name__, e)
            return None

    page, rate, rub, tg = await asyncio.gather(
        safe(svc.fragment.number_page(digits), "fragment"),
        safe(rates.ton_usd(), "rate"), safe(rates.ton_rub(), "rub"),
        svc.tg.phone(digits))
    if not rate and page and page.ton_rate:
        rate = page.ton_rate
    if not rub and rate:
        rub = rate * (await rates.usd_rub())
    return NumberReport(digits, page, rate or 0.0, rub or 0.0, tg)
