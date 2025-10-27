import asyncio
from datetime import datetime, timedelta
import os
from typing import Optional
import httpx
from fastapi import FastAPI, HTTPException, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session
import uvicorn
from gemini_chat import get_gemini_reply, parse_meeting_message
from google_calendar import create_event, ensure_google_files_exist
import models, database, schemas
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv
from io import BytesIO

# =====================================================
# ENVIRONMENT & DATABASE
# =====================================================
load_dotenv()
models.Base.metadata.create_all(bind=database.engine)
app = FastAPI(title="BooksNameFAPI")

ensure_google_files_exist()

print("🔍 GEMINI_API_KEY available?", os.getenv("GEMINI_API_KEY"), bool(os.getenv("GEMINI_API_KEY")))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or "8468933584:AAG1XFuEF3qTq7_wYnppnP5ETHAN_bB5wRY"
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN not found!")

BOT_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
WEBHOOK_URL = (
    f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    if os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    else "http://localhost:8000/webhook"
)

# =====================================================
# DEPENDENCY
# =====================================================
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =====================================================
# SMART MESSAGE SENDER (prevents Telegram 400 errors)
# =====================================================
MAX_LENGTH = 4000

async def send_smart_message(update: Update, text: str):
    """
    Send long messages safely without cutting context.
    Splits by paragraph if needed, or sends as file if too long.
    """
    if len(text) <= MAX_LENGTH:
        await update.message.reply_text(text)
        return

    # Split on paragraphs to preserve readability
    parts = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > MAX_LENGTH:
            parts.append(current)
            current = line
        else:
            current += line
    if current:
        parts.append(current)

    # If too many chunks — send as file
    if len(parts) > 3:
        preview = text[:1000] + "\n\n(Full response attached 👇)"
        await update.message.reply_text(preview)
        bio = BytesIO()
        bio.write(text.encode())
        bio.seek(0)
        await update.message.reply_document(document=bio, filename="gemini_output.txt")
        return

    # Send each part sequentially
    for part in parts:
        await update.message.reply_text(part.strip())

# =====================================================
# TELEGRAM HANDLERS
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! Your FastAPI Telegram bot is live.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Smart handler for normal messages and contextual replies."""
    user_text = update.message.text
    reply_to_msg = update.message.reply_to_message
    last_meeting = context.user_data.get("last_meeting")

    # --- Case 1: Replying to last meeting message ---
    if reply_to_msg and last_meeting and reply_to_msg.message_id == last_meeting["message_id"]:
        user_text_lower = user_text.lower()

        if "cancel" in user_text_lower or "delete" in user_text_lower:
            try:
                from google_calendar import get_calendar_service
                service = get_calendar_service()
                service.events().delete(calendarId="primary", eventId=last_meeting["event_id"]).execute()
                await update.message.reply_text(f"🗑️ Meeting '{last_meeting['title']}' cancelled successfully.")
                context.user_data.pop("last_meeting", None)
            except Exception as e:
                await update.message.reply_text(f"⚠️ Could not cancel meeting: {e}")
            return

        elif "change" in user_text_lower or "reschedule" in user_text_lower:
            reply = "🔁 I can reschedule meetings soon — for now, please delete and recreate it."
            await update.message.reply_text(reply)
            return

        else:
            # Contextual AI response
            prompt = f"""
The user replied to a meeting confirmation message.

Original meeting: "{last_meeting['title']}"
User said: "{user_text}"

Respond helpfully and concisely, keeping context about meetings.
"""
            reply = get_gemini_reply(prompt)
            await send_smart_message(update, reply)
            return

    # --- Case 2: Normal message (no reply) ---
    reply = get_gemini_reply(user_text)
    await send_smart_message(update, reply)
async def schedule_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /schedule command and create a Google Calendar event."""
    user_input = " ".join(context.args)
    if not user_input:
        await update.message.reply_text(
            "Please describe your meeting (e.g. `/schedule a meeting tomorrow at 10 am about project updates`)."
        )
        return

    parsed = parse_meeting_message(user_input)
    title = parsed.get("title") or "Untitled Meeting"
    date = parsed.get("date")
    time = parsed.get("time")

    if not date or not time:
        await update.message.reply_text("I couldn’t find a clear date or time. Could you specify them?")
        return

    # Convert parsed date/time to datetime
    try:
        start_time = datetime.fromisoformat(f"{date}T{time}:00")
    except Exception:
        await update.message.reply_text("⚠️ Invalid date/time format.")
        return

    # Create Google Calendar event
    date_str = start_time.date().isoformat()
    time_str = start_time.time().strftime("%H:%M")
    event = create_event(title, date_str, time_str)
    
    event_link = event.get("htmlLink", "No link available")

    msg = await update.message.reply_text(
        f"✅ Meeting scheduled:\n🗓 {title}\n📅 {date} at {time}\n🔗 {event_link}"
    )

    # Store event metadata for contextual replies
    context.user_data["last_meeting"] = {
        "event_id": event.get("id"),
        "message_id": msg.message_id,
        "title": title,
    }

# =====================================================
# TELEGRAM INITIALIZATION
# =====================================================
telegram_app: Application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("schedule", schedule_meeting))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# =====================================================
# FASTAPI STARTUP / SHUTDOWN
# =====================================================
@app.on_event("startup")
async def on_startup():
    print("🚀 Starting FastAPI app...")

    async with httpx.AsyncClient() as client:
        await client.post(f"{BOT_URL}/deleteWebhook")

    if "RENDER" in os.environ:
        print("🌐 Running on Render — using Webhook mode")
        await telegram_app.initialize()
        await telegram_app.start()
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BOT_URL}/setWebhook", json={"url": WEBHOOK_URL})
            print("📡 Webhook set:", response.json())
    else:
        print("💬 Running locally — using Polling mode")
        await telegram_app.initialize()
        await telegram_app.start()
        asyncio.create_task(telegram_app.run_polling(stop_signals=None))

@app.on_event("shutdown")
async def on_shutdown():
    print("🛑 Shutting down bot...")
    await telegram_app.stop()
    await telegram_app.shutdown()

# =====================================================
# TELEGRAM WEBHOOK ENDPOINT
# =====================================================
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    if not telegram_app.running:
        await telegram_app.initialize()
        await telegram_app.start()
    await telegram_app.process_update(update)
    return {"ok": True}

# =====================================================
# SEND MESSAGE ENDPOINT
# =====================================================
@app.post("/send_message/")
async def send_message(chat_id: int, text: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BOT_URL}/sendMessage", json={"chat_id": chat_id, "text": text})
    return response.json()

# =====================================================
# BOOKS CRUD
# =====================================================
@app.post("/books/", response_model=schemas.BookResponse)
def create_book(book: schemas.BookCreate, db: Session = Depends(get_db)):
    author = db.query(models.Author).filter_by(author_name=book.author_name).first()
    if not author:
        author = models.Author(author_name=book.author_name)
        db.add(author)
        db.commit()
        db.refresh(author)

    existing_book = db.query(models.Book).filter(models.Book.title == book.title).first()
    if existing_book:
        raise HTTPException(status_code=400, detail="Book already exists.")

    new_book = models.Book(
        title=book.title,
        author_id=author.id,
        published_year=book.published_year,
        genre=book.genre,
    )
    db.add(new_book)
    db.commit()
    db.refresh(new_book)

    return schemas.BookResponse(
        id=new_book.id,
        title=new_book.title,
        author_name=author.author_name,
        published_year=new_book.published_year,
        genre=new_book.genre,
    )

@app.get("/books/", response_model=list[schemas.BookResponse])
def list_books(db: Session = Depends(get_db)):
    books = db.query(models.Book).all()
    return [
        schemas.BookResponse(
            id=b.id,
            title=b.title,
            author_name=db.query(models.Author).get(b.author_id).author_name
            if db.query(models.Author).get(b.author_id)
            else "Unknown",
            published_year=b.published_year or 0,
            genre=b.genre or "Unknown",
        )
        for b in books
    ]

@app.delete("/delete-all")
def delete_all_books(db: Session = Depends(get_db)):
    db.query(models.Book).delete()
    seq_name = db.execute(text("SELECT pg_get_serial_sequence('books', 'id')")).scalar()
    db.execute(text(f"ALTER SEQUENCE {seq_name} RESTART WITH 1"))
    db.commit()
    return {"message": "Deleted all records"}

# =====================================================
# USERS CRUD
# =====================================================
@app.get("/user-list", response_model=list[schemas.AddUserResponse])
def get_user_list(db: Session = Depends(get_db)):
    userlist = db.query(models.UserList).all()
    return [
        schemas.AddUserResponse(
            id=a.id, user_id=a.user_id, user_role=a.user_role, username=a.username
        )
        for a in userlist
    ]

@app.post("/create-user")
def create_user(user: schemas.AddUserRequest, db: Session = Depends(get_db)):
    existing_user = db.query(models.UserList).filter(models.UserList.user_id == user.user_id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists.")
    new_user = models.UserList(username=user.username, user_id=user.user_id, user_role=user.user_role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"data": new_user, "message": "User created successfully"}

@app.delete("/delete-all-user")
def delete_all_users(db: Session = Depends(get_db)):
    deleted_count = db.query(models.UserList).delete()
    db.execute(text("""
        SELECT setval(
            pg_get_serial_sequence('userList', 'id'),
            COALESCE((SELECT MAX(id) FROM userList), 0) + 1,
            false
        );
    """))
    db.commit()
    return {"message": f"Deleted all users ({deleted_count} records)."}

# =====================================================
# MAIN ENTRY
# =====================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
