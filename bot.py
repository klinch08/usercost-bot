# -*- coding: utf-8 -*-
"""Бот оценки юзернеймов. Запуск: py -3.13 bot.py (BOT_TOKEN в окружении)."""

import asyncio
import logging
import re
import socket
import sys
from datetime import date

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import (BufferedInputFile, CallbackQuery, ForceReply, InlineKeyboardButton,
                           InlineKeyboardMarkup, InlineQuery, InlineQueryResultArticle,
                           InlineQueryResultCachedPhoto, InputTextMessageContent, Message)

import card
import keepalive
import config
import service
import storage
import texts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

NUMBER = re.compile(r"^\+?\s*888[\d\s()-]{8,14}$")
NICK = re.compile(r"^(?:https?://)?(?:t\.me/|@)?([a-zA-Z][a-zA-Z0-9_]{3,31})/?$")

dp = Dispatcher()
svc: service.Service = None
db: storage.Storage = None
ME = "UsernameCost_bot"


def keyboard(name):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Оценить ещё", callback_data="again"),
         InlineKeyboardButton(text="📤 Поделиться", switch_inline_query=name)],
    ])


@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("👋 Пришлите юзернейм — <code>@ник</code> или просто <code>ник</code>, "
                   "и я оценю его стоимость по реальным продажам Fragment.\n\n"
                   "Без лимитов.")


@dp.message(F.text)
async def evaluate(m: Message):
    if NUMBER.match(m.text.strip()):
        digits = re.sub(r"\D", "", m.text)
        if len(digits) != 11:
            await m.answer("Анонимный номер Fragment — это +888 и ещё 8 цифр.")
            return
        await m.bot.send_chat_action(m.chat.id, "typing")
        rep = await service.number_report(svc, digits)
        await m.answer(texts.number_text(rep), disable_web_page_preview=True,
                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                           text="🔄 Оценить ещё", callback_data="again")]]))
        return
    found = NICK.match(m.text.strip())
    if not found:
        await m.answer("Не похоже на юзернейм. Нужно 4–32 символа: латиница, цифры и _, "
                       "начинается с буквы.")
        return
    name = found.group(1).lower()
    await m.bot.send_chat_action(m.chat.id, "upload_photo")
    rep = await svc.report(name)
    r = rep.result
    kb = keyboard(name)

    path = card.cached(name, r.rank, r.stars, r.valuable, ME)
    with open(path, "rb") as f:
        photo = BufferedInputFile(f.read(), filename=name + ".png")
    cap = texts.caption(rep)
    if cap:
        sent = await m.answer_photo(photo, caption=cap, reply_markup=kb)
    else:
        sent = await m.answer_photo(photo)
        await m.answer(texts.full_text(rep), reply_markup=kb, disable_web_page_preview=True)
    await db.save_card("%s:%s" % (name, date.today().isoformat()),
                       sent.photo[-1].file_id, texts.short(rep, ME))


@dp.callback_query(F.data == "again")
async def again(c: CallbackQuery):
    await c.answer()
    await c.message.answer("Пришлите следующий юзернейм:",
                           reply_markup=ForceReply(input_field_placeholder="@username"))


@dp.inline_query()
async def inline(q: InlineQuery):
    found = NICK.match(q.query.strip())
    if not found:
        await q.answer([], cache_time=5, switch_pm_text="Оценить юзернейм", switch_pm_parameter="go")
        return
    name = found.group(1).lower()
    open_bot = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text="Оценить свой ник", url="https://t.me/%s?start=go" % ME)]])
    saved = await db.last_card(name)
    if saved:
        file_id, summary = saved
        result = InlineQueryResultCachedPhoto(id="c" + name, photo_file_id=file_id,
                                              caption=summary, parse_mode="HTML",
                                              reply_markup=open_bot)
    else:
        rep = await svc.report(name)
        result = InlineQueryResultArticle(
            id="a" + name, title="@%s — ранг %d/10" % (name, rep.result.rank),
            description="Отправить оценку в чат",
            input_message_content=InputTextMessageContent(
                message_text=texts.short(rep, ME), parse_mode="HTML"),
            reply_markup=open_bot)
    await q.answer([result], cache_time=300, is_personal=False)


def single_instance():
    """Второй процесс на том же компьютере не стартует: два поллера дают 409."""
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 47831))
    except OSError:
        log.error("бот уже запущен на этом компьютере")
        sys.exit(1)
    return s


async def main():
    global svc, db, ME
    if not config.BOT_TOKEN:
        log.error("нет BOT_TOKEN в окружении")
        return
    lock = single_instance()  # noqa: F841
    keepalive.start()   # Render ждёт, что сервис слушает PORT
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    ME = (await bot.get_me()).username
    db = storage.Storage()
    await db.open()
    svc = service.Service()
    if not svc.tg.enabled:
        log.warning("TG_SESSION не задан: скам-базы и ограничения номеров не проверяются")
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await dp.start_polling(bot)
    finally:
        await svc.close()


if __name__ == "__main__":
    asyncio.run(main())
