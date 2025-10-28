from telegram import Update
from telegram.ext import ContextTypes
from gemini_chat import interpret_command
from google_calendar import (
    update_event_title,
    update_event_time,
    update_event_date,
    create_event
)

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

    # Step 1: Interpret user message using Gemini
    ai_response = interpret_command(user_message)

    # Step 2: Handle structured command cases
    if isinstance(ai_response, dict):
        action = ai_response.get("action")

        # ---------------------------------
        # CASE 1: Schedule new meeting
        # ---------------------------------
        if action == "schedule_meeting":
            details = ai_response.get("details", {})
            if not all(k in details for k in ["title", "date", "time"]):
                await update.message.reply_text("⚠️ Couldn't detect meeting date/time. Please specify clearly.")
                return

            created = create_event(
                title=details["title"],
                date=details["date"],
                time=details["time"],
                attendees=details.get("attendees")
            )

            if created:
                await update.message.reply_text(
                    f"✅ Meeting *{details['title']}* scheduled on {details['date']} at {details['time']}.\n"
                    f"[View in Calendar]({created.get('htmlLink')})",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("❌ Failed to schedule the meeting.")
            return

        # ---------------------------------
        # CASE 2: Update meeting title
        # ---------------------------------
        if action == "update_meeting_title":
            new_title = ai_response.get("new_title")
            if not new_title:
                await update.message.reply_text("⚠️ Please tell me the new title for the meeting.")
                return

            updated = update_event_title(new_title)
            if updated:
                await update.message.reply_text(
                    f"✅ Meeting title changed to *{new_title}*!",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("⚠️ No upcoming meetings found to update.")
            return

        # ---------------------------------
        # CASE 3: Update meeting time
        # ---------------------------------
        if action == "update_meeting_time":
            new_time = ai_response.get("new_time")
            if not new_time:
                await update.message.reply_text("⚠️ Please tell me the new time for the meeting (e.g., 10:00).")
                return

            updated = update_event_time(new_time)
            if updated:
                await update.message.reply_text(
                    f"✅ Meeting time updated to *{new_time}*!",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("⚠️ Couldn't find an upcoming meeting to update.")
            return

        # ---------------------------------
        # CASE 4: Update meeting date
        # ---------------------------------
        if action == "update_meeting_date":
            new_date = ai_response.get("new_date")
            if not new_date:
                await update.message.reply_text("⚠️ Please specify the new date (YYYY-MM-DD).")
                return

            updated = update_event_date(new_date)
            if updated:
                await update.message.reply_text(
                    f"✅ Meeting moved to *{new_date}*!",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("⚠️ Couldn't find an upcoming meeting to update.")
            return

        # ---------------------------------
        # CASE 5: General AI reply
        # ---------------------------------
        reply_text = ai_response.get("reply")
        if reply_text:
            await update.message.reply_text(reply_text)
            return

    # Step 3: If Gemini returns a plain string
    elif isinstance(ai_response, str):
        await update.message.reply_text(ai_response)
        return

    # Step 4: Fallback
    await update.message.reply_text("🤔 I'm not sure how to handle that yet.")