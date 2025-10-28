from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from gemini_chat import parse_meeting_message  # top-level import
from google_calendar import create_event      # top-level import


# =====================================================
# HANDLER: /schedule
# =====================================================
async def schedule_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    attendees = parsed.get("attendees", [])
    past = parsed.get("past", False)

    if not date or not time:
        await update.message.reply_text("⚠️ I couldn’t find a clear date or time. Could you specify them?")
        return

    try:
        start_time = datetime.fromisoformat(f"{date}T{time}:00")
    except Exception:
        await update.message.reply_text("⚠️ Invalid date/time format.")
        return

    # If parse_meeting_message adjusted past time
    if past:
        await update.message.reply_text(
            f"⚠️ The time you mentioned seems to be in the past, "
            f"so I’ve adjusted it to the next available slot.\n"
            f"Would you like to proceed with scheduling **{title}** "
            f"on {date} at {time}? (yes/no)"
        )
        context.user_data["pending_meeting"] = {
            "title": title,
            "date": date,
            "time": time,
            "attendees": attendees,
        }
        return

    # Ensure not scheduling in past
    now = datetime.now()
    if start_time < now:
        await update.message.reply_text("⏰ You can’t schedule meetings in the past! Please choose a future time.")
        return

    # Create event
    event = None
    try:
        event = create_event(title, date, time, attendees=attendees)
    except Exception as e:
        print("Create event error:", e)
        await update.message.reply_text("⚠️ Failed to create the calendar event.")
        return

    if not event:
        await update.message.reply_text("⚠️ Event could not be created.")
        return

    event_link = event.get("htmlLink", "No link available")
    event_id = event.get("id")

    attendees_text = f"👥 Participants: {', '.join(attendees)}\n" if attendees else ""
    msg = await update.message.reply_text(
        f"✅ Meeting scheduled:\n"
        f"🗓 {title}\n📅 {date} at {time}\n"
        f"{attendees_text}🔗 {event_link}"
    )

    context.user_data["last_meeting"] = {
        "event_id": event_id,
        "message_id": msg.message_id,
        "title": title,
        "date": date,
        "time": time,
        "attendees": attendees,
    }
