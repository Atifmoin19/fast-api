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

app = FastAPI(title="Smart Assistant API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

telegram_app = None  # Will hold the Application instance


@app.on_event("startup")
async def startup_event():
    global telegram_app
    print("🚀 Initializing Smart Assistant components...")

    # Gemini init
    setup_gemini()
    print("✅ Gemini API initialized successfully!")

    # Google Calendar check
    try:
        get_calendar_service()
        print("✅ Google Calendar connected successfully!")
    except Exception as e:
        print("⚠️ Google Calendar setup failed:", e)

    # Telegram setup (returns Application)
    telegram_app = setup_telegram_bot(app)
    print("✅ Telegram bot initialized successfully.")

    # Choose webhook vs polling based on RENDER env
    if os.getenv("RENDER", "").lower() == "true":
        render_url = os.getenv("RENDER_EXTERNAL_URL")
        if not render_url:
            raise RuntimeError("Missing RENDER_EXTERNAL_URL")

        full_webhook_url = f"{render_url.rstrip('/')}/webhook"

        try:
            await telegram_app.initialize()
            await telegram_app.start()
            await telegram_app.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(2)  # small warmup
            ok = await telegram_app.bot.set_webhook(full_webhook_url)
            print("✅ Webhook set:", ok)
            info = await telegram_app.bot.get_webhook_info()
            print("ℹ️ Telegram webhook info:", info.to_dict())
        except Exception as e:
            print("⚠️ Failed to set webhook:", e)

    else:
        # Local polling already started in setup, but in case you prefer async method:
        print("💻 Running in local/polling mode (polling started in setup).")


@app.post("/webhook")
async def telegram_webhook(request: Request):
    if not telegram_app:
        return {"ok": False, "error": "Telegram not initialized"}
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}


@app.get("/debug/webhook")
async def debug_webhook():
    if not telegram_app:
        return {"ok": False, "error": "Telegram app not initialized"}
    info = await telegram_app.bot.get_webhook_info()
    return info.to_dict()


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
