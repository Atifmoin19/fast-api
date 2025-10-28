import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from telegram_bot.setup import setup_telegram_bot
from gemini_chat import setup_gemini
from google_calendar import get_calendar_service

# ============================================================
# FASTAPI INITIALIZATION
# ============================================================
app = FastAPI(title="Smart Assistant API", version="1.0")

# Enable CORS for local dev + deployed environments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For now; can be restricted later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# FEATURE SETUP (Telegram + Gemini + Google Calendar)
# ============================================================
@app.on_event("startup")
def startup_event():
    """Initialize all connected services on startup."""
    print("🚀 Initializing Smart Assistant components...")

    # 1️⃣ Setup Gemini API
    setup_gemini()

    # 2️⃣ Verify Google Calendar service
    try:
        service = get_calendar_service()
        print("✅ Google Calendar connected successfully!")
    except Exception as e:
        print("⚠️ Google Calendar setup failed:", e)

    # 3️⃣ Start Telegram bot (background polling)
    setup_telegram_bot(app)

# ============================================================
# ROOT HEALTHCHECK ENDPOINT
# ============================================================
@app.get("/")
def root():
    return {
        "status": "✅ OK",
        "message": "Smart Assistant is running!",
        "telegram": True,
        "calendar": True,
        "gemini": True,
    }

# ============================================================
# STARTUP (LOCAL RUN)
# ============================================================
if __name__ == "__main__":
    import uvicorn

    print("💡 Starting FastAPI + Telegram Bot locally...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
