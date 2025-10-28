from telegram import Update
from telegram.ext import ContextTypes
from gemini_chat import interpret_command
from google_calendar import update_event_title


# =====================================================
# /start command handler
# =====================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I'm your Automation Bot.\n"
        "I can help you schedule and manage meetings, and chat about tech topics.\n\n"
        "Try these:\n"
        "• /schedule meeting tomorrow at 10am with test@gmail.com\n"
        "• Change meeting title to Daily Syncup\n"
        "• Tell me something about React"
    )


# =====================================================
# Natural text + Gemini interpretation handler
# =====================================================
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.strip()

    # Step 1: Send user message to Gemini for intent understanding
    ai_response = interpret_command(user_message)

    # Step 2: Check if Gemini found a structured action
    if isinstance(ai_response, dict):
        action = ai_response.get("action")

        # ---------------------------------
        # CASE 1: Update meeting title
        # ---------------------------------
        if action == "update_meeting_title":
            event_id = ai_response.get("event_id")
            new_title = ai_response.get("new_title")

            if not event_id:
                await update.message.reply_text("⚠️ I couldn’t find which meeting to update.")
                return

            if not new_title:
                await update.message.reply_text("⚠️ Please tell me the new title for the meeting.")
                return

            success = update_event_title(event_id, new_title)

            if success:
                await update.message.reply_text(
                    f"✅ Meeting title successfully changed to *{new_title}*!",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ Failed to update meeting title on Google Calendar.")
            return

        # ---------------------------------
        # CASE 2: General text reply
        # ---------------------------------
        reply_text = ai_response.get("reply")
        if reply_text:
            await update.message.reply_text(reply_text)
            return

    # Step 3: If Gemini returned a plain string response
    elif isinstance(ai_response, str):
        await update.message.reply_text(ai_response)
        return

    # Step 4: Fallback case
    await update.message.reply_text("🤔 I'm not sure how to handle that yet.")
