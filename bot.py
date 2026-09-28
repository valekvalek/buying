"""Telegram-бот для сравнения цен корзины. Запуск: python bot.py"""
from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import config
from llm import LLMError
from parsers.csv_parser import parse_csv
from parsers.image_parser import parse_image
from parsers.text_parser import parse_text
from pipeline import analyze

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bot")

TG_LIMIT = 4000   # максимум символов в одном сообщении Telegram — 4096

HELP = """Пришлите корзину одним из способов:

1) Текстом, по позиции на строку:
Пятёрочка
Молоко Простоквашино 2,5% 930 мл — 2 шт — 89.99 ₽
Хлеб Бородинский Коломенское 400 г — 1 шт — 59.90 ₽

2) Файлом CSV с колонками: название, бренд, фасовка, количество, цена, сервис
3) Скриншотом корзины — только если задан ключ ANTHROPIC_API_KEY (необязательно)

Я сопоставлю товары в Пятёрочке, Самокате, Яндекс Лавке, ВкусВилле и Чижике и посчитаю, где дешевле.

Озон Фреш: пришлите свою корзину оттуда (первой строкой «Озон Фреш») — я запомню цены
и буду учитывать их в следующих сравнениях с пометкой даты. Текущие цены Озона я не вижу.
ВкусВилл — реальные цены, остальные сервисы — mock-данные (вымышленные)."""


def _chunks(text: str) -> list[str]:
    """Режем длинный текст по строкам, чтобы уложиться в лимит Telegram."""
    out, cur = [], ""
    for line in text.split("\n"):
        while len(line) > TG_LIMIT:
            out.append(line[:TG_LIMIT])
            line = line[TG_LIMIT:]
        if len(cur) + len(line) + 1 > TG_LIMIT:
            out.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        out.append(cur)
    return out


async def _run(update: Update, items) -> None:
    if not items:
        await update.message.reply_text("Не нашёл ни одной позиции. Проверьте формат — /help")
        return
    await update.message.reply_text(
        f"Нашёл позиций: {len(items)}. Сопоставляю товары"
        + (" через LLM…" if config.LLM_ENABLED else " по правилам…"))
    try:
        user_id = update.effective_user.id if update.effective_user else None
        messages = await asyncio.to_thread(analyze, items, config.REGION, user_id)
    except Exception:
        log.exception("Ошибка анализа")
        await update.message.reply_text("Произошла ошибка при расчёте. Подробности — в консоли, где запущен бот.")
        return
    for msg in messages:
        for part in _chunks(msg):
            await update.message.reply_text(part)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run(update, parse_text(update.message.text))


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    file = await update.message.photo[-1].get_file()   # самое большое разрешение
    data = bytes(await file.download_as_bytearray())
    await _parse_image_and_run(update, data, "image/jpeg")


async def _parse_image_and_run(update: Update, data: bytes, media_type: str) -> None:
    await update.message.reply_text("Распознаю скриншот…")
    try:
        items = await asyncio.to_thread(parse_image, data, media_type)
    except LLMError as e:
        await update.message.reply_text(f"Не удалось распознать скриншот: {e}")
        return
    await _run(update, items)


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    doc = update.message.document
    name = (doc.file_name or "").lower()
    data = bytes(await (await doc.get_file()).download_as_bytearray())
    if name.endswith(".csv") or doc.mime_type in ("text/csv", "text/comma-separated-values"):
        try:
            items = parse_csv(data)
        except ValueError as e:
            await update.message.reply_text(f"Ошибка в CSV: {e}")
            return
        await _run(update, items)
    elif doc.mime_type in ("image/png", "image/jpeg", "image/webp"):
        await _parse_image_and_run(update, data, doc.mime_type)
    elif name.endswith(".txt"):
        await _run(update, parse_text(data.decode("utf-8-sig", errors="replace")))
    else:
        await update.message.reply_text("Поддерживаются CSV, TXT и изображения (PNG/JPG/WEBP).")


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("Не задан TELEGRAM_BOT_TOKEN. Скопируйте .env.example в .env и впишите токен.")
    if not config.LLM_ENABLED:
        log.info("Работаю без LLM: сопоставление по правилам, скриншоты недоступны.")
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("Бот запущен. Остановить: Ctrl+C")
    app.run_polling()


if __name__ == "__main__":
    main()
