import os
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Rome")
SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "enabled": True,
    "group_chat_id": None,
    "topic_id": None,
    "days": [0],          # 0 = Monday
    "start_hour": 10,
    "end_hour": 12
}


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


settings = load_settings()


def day_names(days):
    names = {
        0: "Mon",
        1: "Tue",
        2: "Wed",
        3: "Thu",
        4: "Fri",
        5: "Sat",
        6: "Sun",
    }
    return ", ".join(names[d] for d in days if d in names)


def is_private_chat(update: Update) -> bool:
    return update.effective_chat is not None and update.effective_chat.type == "private"


def is_allowed_now() -> bool:
    now = datetime.now(ZoneInfo(TIMEZONE))
    return (
        now.weekday() in settings["days"]
        and settings["start_hour"] <= now.hour < settings["end_hour"]
    )


async def cmd_helpbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        return

    text = (
        "Commands:\n"
        "/status - current settings\n"
        "/on - enable moderation\n"
        "/off - disable moderation\n"
        "/setgroup CHAT_ID - set target group id\n"
        "/settopic TOPIC_ID - set target topic id\n"
        "/sethours 10 12 - allowed hours\n"
        "/setdays 0 2 4 - allowed days (0=Mon ... 6=Sun)\n"
        "/helpbot - show commands\n\n"
        "Important:\n"
        "All commands work only here in private chat.\n"
        "In the group the bot will stay silent."
    )
    await update.message.reply_text(text)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        return

    text = (
        f"Bot status: {'ON' if settings['enabled'] else 'OFF'}\n"
        f"Group chat ID: {settings['group_chat_id']}\n"
        f"Topic ID: {settings['topic_id']}\n"
        f"Days: {day_names(settings['days'])}\n"
        f"Hours: {settings['start_hour']:02d}:00 - {settings['end_hour']:02d}:00\n"
        f"Timezone: {TIMEZONE}"
    )
    await update.message.reply_text(text)


async def cmd_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        return
    settings["enabled"] = True
    save_settings(settings)
    await update.message.reply_text("Bot enabled.")


async def cmd_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        return
    settings["enabled"] = False
    save_settings(settings)
    await update.message.reply_text("Bot disabled.")


async def cmd_setgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        return

    if len(context.args) != 1:
        await update.message.reply_text("Use: /setgroup -1001234567890")
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Chat ID must be a number.")
        return

    settings["group_chat_id"] = chat_id
    save_settings(settings)
    await update.message.reply_text(f"Group chat ID saved: {chat_id}")


async def cmd_settopic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        return

    if len(context.args) != 1:
        await update.message.reply_text("Use: /settopic 12345")
        return

    try:
        topic_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Topic ID must be a number.")
        return

    settings["topic_id"] = topic_id
    save_settings(settings)
    await update.message.reply_text(f"Topic ID saved: {topic_id}")


async def cmd_sethours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        return

    if len(context.args) != 2:
        await update.message.reply_text("Use: /sethours 10 12")
        return

    try:
        start = int(context.args[0])
        end = int(context.args[1])
        if not (0 <= start <= 23 and 1 <= end <= 24 and start < end):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Hours must be valid, for example: /sethours 10 12")
        return

    settings["start_hour"] = start
    settings["end_hour"] = end
    save_settings(settings)
    await update.message.reply_text(f"Hours updated: {start:02d}:00 - {end:02d}:00")


async def cmd_setdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        return

    if not context.args:
        await update.message.reply_text("Use: /setdays 0 2 4")
        return

    try:
        days = sorted(set(int(x) for x in context.args))
        if any(d < 0 or d > 6 for d in days):
            raise ValueError
    except ValueError:
        await update.message.reply_text("Days must be numbers from 0 to 6.")
        return

    settings["days"] = days
    save_settings(settings)
    await update.message.reply_text(f"Days updated: {day_names(days)}")


async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat

    if not msg or not chat:
        return

    # Бот ничего не делает в личке обычными сообщениями
    if chat.type == "private":
        return

    thread_id = getattr(msg, "message_thread_id", None)
    user = msg.from_user

    logging.info(
        "Message | chat_id=%s | thread_id=%s | user=%s | text=%s",
        chat.id,
        thread_id,
        user.id if user else None,
        msg.text or msg.caption or "<non-text>"
    )

    if not settings["enabled"]:
        return

    if settings["group_chat_id"] is None or settings["topic_id"] is None:
        return

    # только нужная группа
    if chat.id != settings["group_chat_id"]:
        return

    # только нужный топик
    if thread_id != settings["topic_id"]:
        return

    # не трогаем ботов
    if user and user.is_bot:
        return

    # не трогаем админов
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ("administrator", "creator"):
            return
    except Exception:
        pass

    if not is_allowed_now():
        try:
            await msg.delete()
        except Exception as e:
            logging.exception("Delete failed: %s", e)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("helpbot", cmd_helpbot))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("on", cmd_on))
    app.add_handler(CommandHandler("off", cmd_off))
    app.add_handler(CommandHandler("setgroup", cmd_setgroup))
    app.add_handler(CommandHandler("settopic", cmd_settopic))
    app.add_handler(CommandHandler("sethours", cmd_sethours))
    app.add_handler(CommandHandler("setdays", cmd_setdays))

    app.add_handler(MessageHandler(filters.ALL, handle_group_messages))

    app.run_polling()


if __name__ == "__main__":
    main()