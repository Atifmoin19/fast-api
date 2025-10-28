from io import BytesIO
from telegram import Update

MAX_LENGTH = 4000

async def send_smart_message(update: Update, text: str):
    """
    Sends long messages safely without Telegram 400 errors.
    Splits messages by paragraph or sends as a file if too long.
    """
    if len(text) <= MAX_LENGTH:
        await update.message.reply_text(text)
        return

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

    if len(parts) > 3:
        preview = text[:1000] + "\n\n(Full response attached 👇)"
        await update.message.reply_text(preview)
        bio = BytesIO()
        bio.write(text.encode())
        bio.seek(0)
        await update.message.reply_document(document=bio, filename="gemini_output.txt")
        return

    for part in parts:
        await update.message.reply_text(part.strip())
