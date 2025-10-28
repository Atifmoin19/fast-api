from telegram import Update
from telegram.ext import ContextTypes
from gemini_chat import interpret_command
from google_calendar import update_event_title, update_event_time

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
        "• Change meeting time to 10pm\n"
        "• Tell me something about React"
    )


# =====================================================
# Natural text + Gemini interpretation handler
# =====================================================
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.strip()

    # Step 1: Send user message to Gemini for intent understanding
    ai_response = interpret_command(user_message)

    # Step 2: Check if Gemini returned structured JSON (dict)
    if isinstance(ai_response, dict):
        action = ai_response.get("action")

        # ---------------------------------
        # CASE 1: Update meeting title
        # ---------------------------------
        if action == "update_meeting_title":
            new_title = ai_response.get("new_title")

            if not new_title:
                await update.message.reply_text("⚠️ Please tell me the new title for the meeting.")
                return

            success = update_event_title(new_title)

            if success:
                await update.message.reply_text(
                    f"✅ Meeting title successfully changed to *{new_title}*!",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ Failed to update meeting title on Google Calendar.")
            return

        # ---------------------------------
        # CASE 2: Update meeting time
        # ---------------------------------
        elif action == "update_meeting_time":
            new_time = ai_response.get("new_time")

            if not new_time:
                await update.message.reply_text("⚠️ Please tell me the new time (e.g., 10:00 or 22:00).")
                return

            success = update_event_time(new_time)

            if success:
                await update.message.reply_text(
                    f"🕒 Meeting time successfully changed to *{new_time}*!",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ Failed to update meeting time on Google Calendar.")
            return

        # ---------------------------------
        # CASE 3: General Gemini reply (chat or fallback)
        # ---------------------------------
        reply_text = ai_response.get("reply")
        if reply_text:
            await update.message.reply_text(reply_text)
            return

    # Step 3: If Gemini returned a plain text (string) response
    elif isinstance(ai_response, str):
        await update.message.reply_text(ai_response)
        return

    # Step 4: Default fallback
    await update.message.reply_text("🤔 I'm not sure how to handle that yet.")
