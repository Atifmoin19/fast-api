import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update
from telegram_bot.setup import setup_telegram_bot
from gemini_chat import setup_gemini
from google_calendar import get_calendar_service

# ============================================================
# ENVIRONMENT SETUP
# ============================================================
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

telegram_app = None  # Will hold the ApplicationBuilder instance

# ============================================================
# STARTUP EVENT
# ============================================================
@app.on_event("startup")
async def startup_event():
    """Initialize all connected services on startup."""
    global telegram_app
    print("🚀 Initializing Smart Assistant components...")

    # 1️⃣ Setup Gemini API
    setup_gemini()
    print("✅ Gemini API initialized successfully!")

    # 2️⃣ Verify Google Calendar
    try:
        get_calendar_service()
        print("✅ Google Calendar connected successfully!")
    except Exception as e:
        print("⚠️ Google Calendar setup failed:", e)

    # 3️⃣ Setup Telegram bot
    telegram_app = setup_telegram_bot(app)
    print("✅ Telegram bot initialized successfully.")

    # ============================================================
    #  MODE SELECTION: WEBHOOK (Render) OR POLLING (Local)
    # ============================================================
    if os.getenv("RENDER", "").lower() == "true":
        # 🚀 Webhook mode for Render
        render_url = os.getenv("RENDER_EXTERNAL_URL")
        if not render_url:
            raise RuntimeError("❌ Missing RENDER_EXTERNAL_URL in environment variables.")

        # ✅ Render already gives full https:// URL
        full_webhook_url = f"{render_url.rstrip('/')}/webhook"

        try:
            await telegram_app.initialize()
            await telegram_app.start()
            await telegram_app.bot.delete_webhook(drop_pending_updates=True)

            # Wait briefly for Render SSL to be ready
            await asyncio.sleep(5)

            ok = await telegram_app.bot.set_webhook(full_webhook_url)
            if ok:
                print(f"✅ Webhook set successfully: {full_webhook_url}")
            else:
                print(f"❌ Webhook setup failed for: {full_webhook_url}")

            info = await telegram_app.bot.get_webhook_info()
            print("ℹ️ Telegram webhook info:", info.to_dict())

        except Exception as e:
            print("⚠️ Failed to set webhook:", e)

    else:
        # 💻 Local mode — Polling
        print("💻 Running locally — starting async polling...")
        await telegram_app.bot.delete_webhook(drop_pending_updates=True)

        async def run_polling():
            await telegram_app.initialize()
            await telegram_app.start()
            print("🤖 Telegram polling started!")
            await telegram_app.updater.start_polling()
            await telegram_app.updater.idle()

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
# DEBUG ENDPOINT FOR WEBHOOK STATUS
# ============================================================
@app.get("/debug/webhook")
async def debug_webhook():
    if not telegram_app:
        return {"ok": False, "error": "Telegram app not initialized"}
    info = await telegram_app.bot.get_webhook_info()
    return info.to_dict()


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
        "mode": "webhook" if os.getenv("RENDER", "").lower() == "true" else "polling",
    }


# ============================================================
# LOCAL RUN ENTRY POINT
# ============================================================
if __name__ == "__main__":
    import uvicorn
    print("💡 Starting FastAPI + Telegram Bot locally...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
