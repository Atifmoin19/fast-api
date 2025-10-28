import asyncio
import re
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
    """
    Handles both normal messages and replies.
    If the user replies to a bot message, it keeps context (chat continuation or meeting intent).
    """
    user_text = update.message.text
    reply_to_msg = update.message.reply_to_message
    reply = None

    # 🧩 Case 1: User replied to a bot message
    if reply_to_msg and reply_to_msg.from_user and reply_to_msg.from_user.is_bot:
        prev_text = reply_to_msg.text or ""
        prev_text_lower = prev_text.lower()

        # Detect meeting-related context
        if any(keyword in prev_text_lower for keyword in ["meeting scheduled", "calendar", "🗓", "📅"]):
            prompt = f"""
You are a smart meeting assistant.
The user replied to a message about a scheduled meeting.

Previous bot message:
"{prev_text}"

User's reply:
"{user_text}"

Understand if the user wants to cancel, reschedule, or clarify meeting details.
If yes, respond appropriately (e.g., confirm cancellation or reschedule suggestion).
If not, respond briefly and politely.
"""
        else:
            # Regular chat continuation
            prompt = f"""
Continue this conversation naturally.

The bot previously said:
"{prev_text}"

User replied with:
"{user_text}"

Respond in a natural, conversational tone.
"""
        try:
            reply = get_gemini_reply(prompt)
        except Exception as e:
            print("Gemini context error:", e)
            reply = "⚠️ I couldn’t process your reply right now. Please try again."

    # 💬 Case 2: New message (not a reply)
    else:
        try:
            reply = get_gemini_reply(user_text)
        except Exception as e:
            print("Gemini chat error:", e)
            reply = "⚠️ Something went wrong while generating a response."

    # ✉️ Send message safely (handles Telegram 400 / long messages)
    if not reply:
        reply = "I’m not sure how to respond — could you clarify?"
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
        await update.message.reply_text("⚠️ I couldn’t find a clear date or time. Could you specify them?")
        return

    # Convert parsed date/time to datetime
    try:
        start_time = datetime.fromisoformat(f"{date}T{time}:00")
    except Exception:
        await update.message.reply_text("⚠️ Invalid date/time format.")
        return

    # 🚫 Reject meetings in the past
    now = datetime.now()
    if start_time < now:
        await update.message.reply_text("⏰ You can’t schedule meetings in the past! Please choose a future time.")
        return

    # ✉️ Extract participant emails (e.g. "with atif@gmail.com and moon@gmail.com")
    email_pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
    attendees = re.findall(email_pattern, user_input)

    # 🗓 Create Google Calendar event safely
    date_str = start_time.date().isoformat()
    time_str = start_time.time().strftime("%H:%M")
    event = None

    try:
        # If your create_event supports attendees, pass them
        if "attendees" in create_event.__code__.co_varnames:
            event = create_event(title, date_str, time_str, attendees=attendees)
        else:
            event = create_event(title, date_str, time_str)
    except Exception as e:
        print("Create event error:", e)
        await update.message.reply_text("⚠️ Failed to create the calendar event.")
        return

    # ✅ Handle both dict and string responses
    event_link = "No link available"
    event_id = None
    if isinstance(event, dict):
        event_link = event.get("htmlLink", "No link available")
        event_id = event.get("id")
    elif isinstance(event, str):
        event_link = event

    # 📨 Build reply
    attendees_text = f"👥 Participants: {', '.join(attendees)}\n" if attendees else ""
    msg = await update.message.reply_text(
        f"✅ Meeting scheduled:\n🗓 {title}\n📅 {date} at {time}\n"
        f"{attendees_text}🔗 {event_link}"
    )

    # 🧠 Store meeting context for future replies
    context.user_data["last_meeting"] = {
        "event_id": event_id,
        "message_id": msg.message_id,
        "title": title,
        "date": date,
        "time": time,
        "attendees": attendees,
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
