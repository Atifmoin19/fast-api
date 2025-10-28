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
def setup_telegram_bot(app):
    """
    Initializes Telegram bot and runs polling safely in the background.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("❌ Missing TELEGRAM_TOKEN in environment variables!")

    # Create bot application
    application = ApplicationBuilder().token(token).build()

    # ===============================
    # Register Command Handlers
    # ===============================
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("schedule", schedule_meeting))
    application.add_handler(CommandHandler("chat", echo))

    # ===============================
    # Natural Chat Handler
    # ===============================
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # ===============================
    # Run bot in background thread
    # ===============================
    def run_bot():
        print("🤖 Telegram bot polling started successfully!")
        # Disable signal handling to avoid "set_wakeup_fd" error
        application.run_polling(stop_signals=None)

    thread = threading.Thread(target=run_bot, daemon=True)
    thread.start()
