import asyncio
import os
from typing import Optional
import httpx
from fastapi import FastAPI, HTTPException, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session
import uvicorn

import models, database, schemas
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from dotenv import load_dotenv
load_dotenv()
# =====================================================
# DATABASE INIT
# =====================================================
models.Base.metadata.create_all(bind=database.engine)
app = FastAPI(title="BooksNameFAPI")


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
# TELEGRAM CONFIG
# =====================================================
TELEGRAM_TOKEN = "8468933584:AAG1XFuEF3qTq7_wYnppnP5ETHAN_bB5wRY"
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN not found!")

BOT_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Auto-switch between Render & local
WEBHOOK_URL = (
    f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    if os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    else "http://localhost:8000/webhook"
)


# =====================================================
# TELEGRAM HANDLERS
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! Your FastAPI Telegram bot is live.")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(f"You said: {text}")


# =====================================================
# SEND MESSAGE ENDPOINT
# =====================================================
@app.post("/send_message/")
async def send_message(chat_id: int, text: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BOT_URL}/sendMessage", json={"chat_id": chat_id, "text": text}
        )
    return response.json()


# =====================================================
# TELEGRAM WEBHOOK ENDPOINT
# =====================================================
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, app.bot.bot)
    await app.bot.process_update(update)
    return {"ok": True}


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
    response = []
    for book in books:
        author = db.query(models.Author).filter_by(id=book.author_id).first()
        response.append(
            schemas.BookResponse(
                id=book.id,
                title=book.title,
                author_name=author.author_name if author else "Unknown",
                published_year=book.published_year or 0,
                genre=book.genre or "Unknown",
            )
        )
    return response


@app.delete("/delete-books")
def delete_book(book: schemas.BookResponse, db: Session = Depends(get_db)):
    new_book = db.query(models.Book).filter(models.Book.id == book.id).first()
    if not new_book:
        return {"error": "No record found for this book"}
    db.delete(new_book)
    db.commit()
    return {"message": "Deleted Record", "data": new_book}


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
@app.get("/authors/", response_model=list[schemas.AuthorResponse])
def list_authors(db: Session = Depends(get_db)):
    authors = db.query(models.Author).all()
    return [schemas.AuthorResponse(id=a.id, author_name=a.author_name) for a in authors]


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
    existing_user = (
        db.query(models.UserList).filter(models.UserList.user_id == user.user_id).first()
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists.")
    new_user = models.UserList(
        username=user.username, user_id=user.user_id, user_role=user.user_role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"data": new_user, "message": "User created successfully"}


@app.delete("/delete-all-user")
def delete_all_users(user: Optional[schemas.AddUserRequest] = None, db: Session = Depends(get_db)):
    if not user:
        deleted_count = db.query(models.UserList).delete()
        sql = text("""
            SELECT setval(
                pg_get_serial_sequence('userList', 'id'),
                COALESCE((SELECT MAX(id) FROM userList), 0) + 1,
                false
            );
        """)
        db.execute(sql)
        db.commit()
        return {"message": f"Deleted all users ({deleted_count} records)."}

    existing_user = db.query(models.UserList).filter(models.UserList.user_id == user.user_id).first()
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(existing_user)
    db.execute(text("""
        SELECT setval(
            pg_get_serial_sequence('userList', 'id'),
            COALESCE((SELECT MAX(id) FROM userList), 0) + 1,
            false
        );
    """))
    db.commit()
    return {"message": "Deleted Record"}


# =====================================================
# STARTUP / SHUTDOWN
# =====================================================
@app.on_event("startup")
async def startup_event():
    print("🤖 Starting Telegram bot...")
    app.bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.bot.add_handler(CommandHandler("start", start))
    app.bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    async with httpx.AsyncClient() as client:
        # Always delete existing webhook first (avoids conflict)
        await client.post(f"{BOT_URL}/deleteWebhook")

    if "RENDER" in os.environ:
        # Running in Render
        print("🌐 Running on Render (Webhook mode)")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BOT_URL}/setWebhook",
                json={"url": WEBHOOK_URL}
            )
            print("📡 Webhook set response:", response.json())
    else:
        # Running locally
        print("💬 Running locally in polling mode...")
        await app.bot.initialize()
        await app.bot.start()
        await app.bot.updater.initialize()
        asyncio.create_task(app.bot.updater.start_polling())


@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 Shutting down bot...")
    if hasattr(app, "bot"):
        await app.bot.updater.stop()
        await app.bot.updater.shutdown()
        await app.bot.stop()
        await app.bot.shutdown()

# =====================================================
# MAIN ENTRY
# =====================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
