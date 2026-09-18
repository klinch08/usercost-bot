# -*- coding: utf-8 -*-
"""Текст ответа в HTML. Структура повторяет эталон из задачи."""

import re
from datetime import date
from html import escape

import fragment

CAPTION_LIMIT = 1024


def ton(x):
    x = round(x, 1)
    s = "{:,}".format(int(x) if x == int(x) else x)
    return s.replace(",", " ")


def money(x, rate):
    usd = ""
    if rate:
        v = x * rate
        usd = " (~$%s)" % (("{:,}".format(int(v)) if v < 1000 else "{:,}".format(round(v)))
                          .replace(",", " "))
    return "%s GRAM (TON)%s" % (ton(x), usd)


def link(name):
    return '<a href="https://t.me/%s">@%s</a>' % (name, name)


def bar(rank):
    return "▰" * rank + "▱" * (10 - rank)


def stars(n):
    return "⭐" * n + "☆" * (5 - n)


def _date(iso):
    try:
        return date.fromisoformat(iso).strftime("%d.%m.%Y")
    except ValueError:
        return iso


def status_lines(rep):
    p, rate = rep.page, rep.rate
    if p is None:
        lines = ["⚠️ Данные Fragment недоступны"]
    elif p.status == fragment.ABSENT:
        lines = ["❌ Продаж на Fragment не обнаружено"]
    elif p.status == fragment.ON_AUCTION:
        lines = ["🔨 На аукционе, текущая ставка: " + money(p.price, rate)]
    elif p.status == fragment.FOR_SALE:
        lines = ["🏷 Продаётся без аукциона: " + money(p.price, rate)]
    elif p.status == fragment.SOLD:
        when = " (%s)" % _date(p.history[0].date) if p.history and p.history[0].date else ""
        lines = ["✅ Продан на Fragment за " + money(p.price, rate) + when]
    elif p.status == fragment.TAKEN:
        lines = ["👤 Занят владельцем, на Fragment не выставлен"]
    else:
        lines = ["❔ Статус на Fragment не распознан"]
    if p is not None and p.history and p.status != fragment.SOLD:
        last = p.history[0]
        lines.append("💸 Последняя продажа: %s (%s)" % (money(last.price, rate), _date(last.date)))
    lines.append(scam_line(rep.tg))

    return lines


def rub(x, rate):
    return "~%s ₽" % "{:,}".format(round(x * rate)).replace(",", " ")


def scam_line(tg):
    """Скам-базы = пометки самого Telegram у владельца ника."""
    if tg is None:
        return "⚠️ Скам-базы: проверка сейчас недоступна"
    if not tg.get("found"):
        return "🛡 Скам-базы: ник никому не принадлежит, отметок нет"
    if tg["scam"]:
        return "🚨 Скам-базы: владелец помечен Telegram как <b>SCAM</b>"
    if tg["fake"]:
        return "🚨 Скам-базы: владелец помечен Telegram как <b>FAKE</b>"
    if tg["restricted"]:
        return "⛔ Скам-базы: аккаунт владельца ограничен Telegram"
    return "🛡 Скам-базы: владелец не найден в скам-базах"


def restriction_line(tg):
    if tg is None:
        return "⚠️ Проверка сейчас недоступна"
    if not tg.get("found"):
        return "❔ Аккаунт на номере не найден или скрыт настройками приватности"
    marks = [m for m, on in (("SCAM", tg["scam"]), ("FAKE", tg["fake"])) if on]
    if tg["restricted"]:
        reasons = ", ".join(escape(r) for r in tg["reasons"]) or "причина не указана"
        marks.append("ограничен (%s)" % reasons)
    return ("⛔ " + ", ".join(marks)) if marks else "✅ Ограничений нет"


def format_number(digits):
    return "+888 %s %s" % (digits[3:7], digits[7:])


def number_text(rep):
    p, rate = rep.page, rep.rate
    out = ["<b>📱 Анонимный номер %s</b>" % format_number(rep.digits), "",
           "<b>📊 Статус на Fragment</b>"]
    price = 0.0
    if p is None:
        out.append("⚠️ Данные Fragment недоступны")
    elif p.status == fragment.ABSENT:
        out.append("❌ Номера нет на Fragment")
    elif p.status == fragment.ON_AUCTION:
        price = p.price
        out.append("🔨 На аукционе, текущая ставка: " + money(p.price, rate))
    elif p.status == fragment.FOR_SALE:
        price = p.price
        out.append("🏷 Продаётся без аукциона: " + money(p.price, rate))
    elif p.status == fragment.SOLD:
        price = p.price
        out.append("✅ Цена продажи: " + money(p.price, rate))
    else:
        out.append("👤 Номер у владельца, не выставлен")
    if price and rep.rub:
        out.append("🇷🇺 В рублях: <b>%s</b>" % rub(price, rep.rub))

    sales = [h for h in (p.history if p else []) if h.price]
    if sales:
        out += ["", "<b>💸 История продаж:</b>", "<blockquote>%s</blockquote>" % "\n".join(
            "• %s — %s" % (_date(h.date), money(h.price, rate)) for h in sales[:5])]

    out += ["", "<b>🛡 Ограничения в Telegram</b>", restriction_line(rep.tg)]
    return "\n".join(out)


def full_text(rep, similar_limit=5, points_limit=10):
    r, rate = rep.result, rep.rate
    out = ["<b>📊 Статус на Fragment</b>"] + status_lines(rep)
    out += ["", "<b>📈 Оценка юзернейма %s</b>" % link(r.name), ""]
    if r.valuable:
        out.append("💰 Оценочная стоимость: <b>%s</b>" % money(r.price_ton, rate))
    else:
        out.append("💰 Юзернейм не представляет ценности для перепродажи")
    out.append("🏷 Стоимость создания: " + money(r.creation_ton, rate))
    out.append("🏆 Ранг: %s %d/10" % (bar(r.rank), r.rank))
    out.append("⭐ Потенциал: " + stars(r.stars))

    if "fragment_search" in rep.errors:
        out += ["", "<b>📋 Похожие продажи на Fragment:</b>", "⚠️ Данные Fragment недоступны"]
    elif r.similar:
        items = ["• %s — %s (длина: %d)" % (link(n), money(p, rate), len(n))
                 for n, p in r.similar[:similar_limit]]
        out += ["", "<b>📋 Похожие продажи на Fragment:</b>",
                "<blockquote>%s</blockquote>" % "\n".join(items)]

    title, points = (("✅ Преимущества:", r.pros) if r.valuable else ("❌ Недостатки:", r.cons))
    if points:
        out += ["", "<b>%s</b>" % title,
                "<blockquote>%s</blockquote>" % "\n".join(map(escape, points[:points_limit]))]

    note = None
    if not r.valuable:
        note = ("⚠️ Это технический вывод: такой юзернейм — случайный набор символов без "
                "спроса на вторичном рынке, поэтому он не стоит дороже цены создания. "
                "Оценка может меняться по мере обновления алгоритмов.")
        if r.feats and not r.feats.random_letters:
            note = note.replace("такой юзернейм — случайный набор символов без спроса",
                                "у такого юзернейма нет подтверждённого спроса")
    if rep.rub:
        amount = r.price_ton if r.valuable else r.creation_ton
        out += ["", "🇷🇺 В рублях: <b>%s</b>" % rub(amount, rep.rub)]
    if note:
        out += ["", "<i>%s</i>" % note]
    return "\n".join(out)


def visible_len(html):
    return len(re.sub(r"<[^>]+>", "", html).replace("&amp;", "&").replace("&lt;", "<")
               .replace("&gt;", ">"))


def caption(rep):
    """Самый полный вариант, который влезает в подпись к фото (1024 символа)."""
    for sim, pts in ((5, 10), (5, 5), (3, 4), (3, 3), (2, 2)):
        t = full_text(rep, sim, pts)
        if visible_len(t) <= CAPTION_LIMIT:
            return t
    return None


def short(rep, bot_username):
    r = rep.result
    value = money(r.price_ton, rep.rate) if r.valuable else "не дороже создания"
    return ("<b>%s</b> — %s\n🏆 Ранг %d/10 · %s\n\nОценка от @%s"
            % (link(r.name), value, r.rank, stars(r.stars), bot_username))
