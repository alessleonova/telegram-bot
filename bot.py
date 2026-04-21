import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Rome")

# Если переменная не задана, бот просто будет писать thread id в лог
ALLOWED_TOPIC_ID = os.getenv("ALLOWED_TOPIC_ID")
ALLOWED_TOPIC_ID = int(ALLOWED_TOPIC_ID) if ALLOWED_TOPIC_ID else None

# 0 = Monday
ALLOWED_WEEKDAY = int(os.getenv("ALLOWED_WEEKDAY", "0"))
START_HOUR = int(os.getenv("START_HOUR", "10"))
END_HOUR = int(os.getenv("END_HOUR", "12"))

def is_allowed_now() -> bool:
    now = datetime.now(ZoneInfo(TIMEZONE))
    return now.weekday() == ALLOWED_WEEKDAY and START_HOUR <= now.hour < END_HOUR

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return

    thread_id = getattr(msg, "message_thread_id", None)
    text = msg.text or msg.caption or "<non-text>"

    logging.info("Message received | thread_id=%s | text=%s", thread_id, text)

    # Сначала просто логируем ID топика
    if ALLOWED_TOPIC_ID is None:
        return

    # Не трогаем сообщения вне нужного топика
    if thread_id != ALLOWED_TOPIC_ID:
        return

    # В нужном топике удаляем всё вне разрешённого времени
    if not is_allowed_now():
        try:
            await msg.delete()
            logging.info("Deleted message in restricted time | thread_id=%s", thread_id)
        except Exception as e:
            logging.exception("Failed to delete message: %s", e)

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()