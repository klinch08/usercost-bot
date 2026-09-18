# -*- coding: utf-8 -*-
"""Метки Telegram: SCAM/FAKE у владельца ника и ограничения аккаунта на номере.

Скам-база здесь - собственные пометки Telegram (флаги scam, fake, restricted),
других открытых баз нет. Нужна сессия аккаунта в TG_SESSION.

Клиент живёт в одном выделенном потоке со своим циклом событий: вызов
Telethon из чужого цикла падает с "There is no current event loop".
На FloodWait молчим ровно столько, сколько сказал Telegram.
"""

import asyncio
import logging
import threading
import time

import config

log = logging.getLogger("tginfo")
CACHE_SEC = 30 * 60


class TgInfo:
    def __init__(self, session=config.TG_SESSION):
        self.session = session
        self._client = None
        self._last = 0.0
        self._silent_until = 0.0
        self._cache = {}
        self._loop = None
        if session:
            self._loop = asyncio.new_event_loop()
            threading.Thread(target=self._loop.run_forever, name="telethon", daemon=True).start()

    @property
    def enabled(self):
        return bool(self.session)

    async def _connect(self):
        if self._client is None:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            self._client = TelegramClient(StringSession(self.session),
                                          config.TG_API_ID, config.TG_API_HASH)
            await self._client.connect()
        return self._client

    async def _pace(self):
        wait = config.CHECK_USERNAME_GAP - (time.time() - self._last)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last = time.time()

    @staticmethod
    def _flags(entity):
        reasons = [r.text for r in (getattr(entity, "restriction_reason", None) or [])]
        return {"found": True,
                "kind": "bot" if getattr(entity, "bot", False) else
                        ("channel" if hasattr(entity, "broadcast") else "user"),
                "scam": bool(getattr(entity, "scam", False)),
                "fake": bool(getattr(entity, "fake", False)),
                "restricted": bool(getattr(entity, "restricted", False)),
                "reasons": reasons}

    async def _username(self, name):
        """Выполняется только в потоке telethon."""
        from telethon import errors
        from telethon.tl.functions.contacts import ResolveUsernameRequest
        client = await self._connect()
        await self._pace()
        try:
            res = await client(ResolveUsernameRequest(name))
        except (errors.UsernameNotOccupiedError, errors.UsernameInvalidError):
            return {"found": False}
        entity = (res.users or res.chats or [None])[0]
        return self._flags(entity) if entity else {"found": False}

    async def _phone(self, digits):
        from telethon import errors
        from telethon.tl.functions.contacts import ResolvePhoneRequest
        client = await self._connect()
        await self._pace()
        try:
            res = await client(ResolvePhoneRequest(digits))
        except (errors.PhoneNotOccupiedError, errors.PhoneNumberInvalidError):
            return {"found": False}
        return self._flags(res.users[0]) if res.users else {"found": False}

    async def _run(self, key, factory):
        if not self.enabled or time.time() < self._silent_until:
            return None
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < CACHE_SEC:
            return hit[1]
        fut = asyncio.run_coroutine_threadsafe(factory(), self._loop)
        try:
            result = await asyncio.wrap_future(fut)
        except Exception as e:
            if type(e).__name__ == "FloodWaitError":
                self._silent_until = time.time() + e.seconds
                log.warning("FloodWait %s с", e.seconds)
            else:
                log.error("%s: %s: %s", key, type(e).__name__, e)
            return None
        self._cache[key] = (time.time(), result)
        return result

    async def username(self, name):
        """dict с флагами, {"found": False} или None, если проверить не вышло."""
        return await self._run("u:" + name, lambda: self._username(name))

    async def phone(self, digits):
        return await self._run("p:" + digits, lambda: self._phone(digits))
