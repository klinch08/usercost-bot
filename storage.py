# -*- coding: utf-8 -*-
"""Отслеживание и file_id карточек. Postgres по DATABASE_URL, иначе SQLite."""

import json

import config

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS watches (
         user_id BIGINT NOT NULL, name TEXT NOT NULL, state TEXT NOT NULL DEFAULT '{}',
         PRIMARY KEY (user_id, name))""",
    """CREATE TABLE IF NOT EXISTS cards (
         key TEXT PRIMARY KEY, file_id TEXT NOT NULL, summary TEXT NOT NULL)""",
]


class Storage:
    async def open(self):
        if config.DATABASE_URL:
            import asyncpg
            self.pg = await asyncpg.create_pool(config.DATABASE_URL, min_size=1, max_size=3)
            self.db = None
        else:
            import aiosqlite
            self.pg = None
            self.db = await aiosqlite.connect(config.SQLITE_PATH)
        for q in SCHEMA:
            await self._exec(q)

    async def _exec(self, q, *args):
        if self.pg:
            n = iter(range(1, 99))
            q = "".join("$%d" % next(n) if ch == "?" else ch for ch in q)
            await self.pg.execute(q, *args)
        else:
            await self.db.execute(q, args)
            await self.db.commit()

    async def _fetch(self, q, *args):
        if self.pg:
            n = iter(range(1, 99))
            q = "".join("$%d" % next(n) if ch == "?" else ch for ch in q)
            return [tuple(r) for r in await self.pg.fetch(q, *args)]
        async with self.db.execute(q, args) as cur:
            return await cur.fetchall()

    async def watch(self, user_id, name, state):
        await self._exec("INSERT INTO watches (user_id, name, state) VALUES (?, ?, ?) "
                         "ON CONFLICT (user_id, name) DO UPDATE SET state = excluded.state",
                         user_id, name, json.dumps(state))

    async def unwatch(self, user_id, name):
        await self._exec("DELETE FROM watches WHERE user_id = ? AND name = ?", user_id, name)

    async def is_watched(self, user_id, name):
        return bool(await self._fetch("SELECT 1 FROM watches WHERE user_id = ? AND name = ?",
                                      user_id, name))

    async def all_watches(self):
        return [(u, n, json.loads(s)) for u, n, s in
                await self._fetch("SELECT user_id, name, state FROM watches")]

    async def user_watches(self, user_id):
        return [r[0] for r in await self._fetch(
            "SELECT name FROM watches WHERE user_id = ? ORDER BY name", user_id)]

    async def save_card(self, key, file_id, summary):
        await self._exec("INSERT INTO cards (key, file_id, summary) VALUES (?, ?, ?) "
                         "ON CONFLICT (key) DO UPDATE SET file_id = excluded.file_id, "
                         "summary = excluded.summary", key, file_id, summary)

    async def last_card(self, name):
        rows = await self._fetch("SELECT file_id, summary FROM cards WHERE key LIKE ? "
                                 "ORDER BY key DESC LIMIT 1", name + ":%")
        return rows[0] if rows else None
