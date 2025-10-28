import os
import threading
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

# Import handlers
from telegram_bot.handlers.message_handler import start, echo
from telegram_bot.handlers.schedule_handler import schedule_meeting

load_dotenv()

# =====================================================
# TELEGRAM BOT INITIALIZATION
# =====================================================
def setup_telegram_bot(app=None):
    """
    Initializes Telegram bot and returns the Application instance.
    Polling or webhook handling is managed externally in main.py.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("❌ Missing TELEGRAM_TOKEN in environment variables!")

    # Create bot application
    application = ApplicationBuilder().token(token).build()

    # Register Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("schedule", schedule_meeting))
    application.add_handler(CommandHandler("chat", echo))

    # Natural Chat Handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("✅ Telegram bot initialized successfully.")
    return application  # 👈 no polling here