import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update
from telegram_bot.setup import setup_telegram_bot
from gemini_chat import setup_gemini
from google_calendar import get_calendar_service

load_dotenv()

# ============================================================
# FASTAPI INITIALIZATION
# ============================================================
app = FastAPI(title="Smart Assistant API", version="1.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# CONDITIONAL TELEGRAM SETUP
# ============================================================
telegram_app = None  # Will hold the ApplicationBuilder instance

@app.on_event("startup")
async def startup_event():
    """Initialize all connected services on startup."""
    global telegram_app
    print("🚀 Initializing Smart Assistant components...")

    # 1️⃣ Setup Gemini API
    setup_gemini()

    # 2️⃣ Verify Google Calendar
    try:
        get_calendar_service()
        print("✅ Google Calendar connected successfully!")
    except Exception as e:
        print("⚠️ Google Calendar setup failed:", e)

    # 3️⃣ Setup Telegram bot
    telegram_app = setup_telegram_bot(app)
    print("✅ Telegram bot initialized successfully.")

    # ===========================
    # Webhook (Render)
    # ===========================
    if os.getenv("RENDER"):
        render_url = os.getenv("RENDER_EXTERNAL_URL")
        if not render_url.startswith("https://"):
            render_url = f"https://{render_url}"

        webhook_url = f"{render_url}/webhook"
        await telegram_app.bot.set_webhook(webhook_url)
        print(f"✅ Webhook set to: {webhook_url}")
    else:
        # ===========================
        # Local Polling
        # ===========================
        await telegram_app.bot.delete_webhook(drop_pending_updates=True)
        print("💻 Webhook cleared, starting async polling...")

        async def run_polling():
            print("🤖 Telegram polling started (local mode)!")
            await telegram_app.run_polling(stop_signals=None)

        asyncio.create_task(run_polling())

# ============================================================
# TELEGRAM WEBHOOK ENDPOINT (Render only)
# ============================================================
@app.post("/webhook")
async def telegram_webhook(request: Request):
    if not telegram_app:
        return {"ok": False, "error": "Telegram not initialized"}
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}


# ============================================================
# ROOT HEALTHCHECK ENDPOINT
# ============================================================
@app.get("/")
def root():
    return {
        "status": "✅ OK",
        "message": "Smart Assistant is running!",
        "telegram": bool(telegram_app),
        "calendar": True,
        "gemini": True,
        "mode": "webhook" if os.getenv("RENDER") else "polling",
    }


# ============================================================
# LOCAL RUN ENTRY POINT
# ============================================================
if __name__ == "__main__":
    import uvicorn
    print("💡 Starting FastAPI + Telegram Bot locally...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
