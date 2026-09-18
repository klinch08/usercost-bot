# UserCost — оценка Telegram-юзернеймов по продажам Fragment

Бот `@UsernameCost_bot`. Присылаешь ник — получаешь карточку, оценку, ранг,
похожие продажи и проверку, можно ли занять ник в Telegram.

## Модули

| файл | что делает |
|---|---|
| `fragment.py` | страница ника, поиск проданных по префиксу, кэш 15 мин, не чаще 2 запросов/с, пауза на 429 |
| `rates.py` | курс TON→USD: CoinGecko, запасной Binance, запасной `tonRate` со страницы Fragment; кэш 5 мин |
| `tgcheck.py` | `account.CheckUsername` через Telethon в отдельном потоке со своим циклом событий |
| `features.py` | признаки ника: слово, бренд, имя, транслит, произносимость, цифры, повторы |
| `valuation.py` | оценка: медиана класса × поправки, смешивание с похожими и собственными продажами |
| `calibrate.py` | пересчёт `data/calibration.json` по снимку продаж (`--refresh` — обновить снимок) |
| `texts.py`, `card.py` | текст ответа (HTML) и карточка 1080×1080 |
| `storage.py` | отслеживание и file_id карточек: Postgres по `DATABASE_URL`, иначе SQLite |
| `bot.py` | aiogram: ответы, кнопки, inline-режим, фоновая проверка отслеживаемых |

## Что делает Fragment (DevTools)

- `GET /username/<ник>` — статус (`On auction`, `For sale`, `Sold`, `Taken`),
  цены, `Ownership History`; ника нет на Fragment — `302` на `/?query=<ник>`.
- `GET /?query=<q>&filter=sold&sort=price_asc` с заголовком `X-Aj-Referer` —
  JSON `{"h": html}`: так сайт сам ходит между страницами. Без заголовка — HTML.
- `POST /api?hash=...` (`hash` из `ajInit`) — подгрузка «Show more»;
  без cookie сессии отвечает `Bad request`, поэтому не используется.
- Цена создания 10 TON — не минимальная ставка (у перепродаж она бывает 2 TON),
  а самая частая цена продажи случайных ников: берётся из живой выдачи поиска.

## Запуск

```
py -3.13 -m pip install -r requirements.txt
set BOT_TOKEN=...
set TG_SESSION=...        (строка из busik\make_session.py, без неё проверка Telegram выключена)
py -3.13 bot.py
```

Или `run.bat` — берёт токен из `token.txt`, если переменной нет.
Один процесс на токен: второй поллер даёт `409 Conflict`.

Inline-режим («Поделиться») нужно включить в @BotFather: `/setinline`.

## Тесты

`py -3.13 -m pytest -q -s tests` — 40 реально проданных ников, сами они
из подгонки исключены. Проверяются корреляция рангов, порядок пар с
разницей цены ≥10× и рост оценки по ценовым группам.
