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


def setup_telegram_bot(app=None):
    """
    Initializes Telegram Application.
    - returns application instance (for webhook use in main.py).
    - if not in RENDER env, also starts polling in a background thread.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("❌ Missing TELEGRAM_TOKEN in environment variables!")

    application = ApplicationBuilder().token(token).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("schedule", schedule_meeting))
    application.add_handler(CommandHandler("chat", echo))

    # Natural chat messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Initialize a shared mapping store for message->event
    # Use application.bot_data for cross-handler shared storage
    application.bot_data.setdefault("event_map", {})

    # If running locally (no RENDER env), start polling in background thread
    if not os.getenv("RENDER", "").lower() == "true":
        def run_bot():
            # disable default signal handling in background thread
            application.run_polling(stop_signals=None)

        thread = threading.Thread(target=run_bot, daemon=True)
        thread.start()
        print("🤖 Telegram bot polling started (local mode)")

    return application
