from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from gemini_chat import parse_meeting_message
from google_calendar import create_event


async def schedule_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /schedule command — creates a new meeting and suggests possible actions."""
    user_input = " ".join(context.args)
    if not user_input:
        await update.message.reply_text(
            "🗓 Please describe your meeting.\n\nExample:\n"
            "`/schedule meeting tomorrow at 10 am about project updates`",
            parse_mode="Markdown"
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

    # If parsed time is in the past
    if past:
        await update.message.reply_text(
            f"⚠️ The mentioned time seems to be in the past.\n"
            f"Would you like to schedule *{title}* on {date} at {time}? (yes/no)",
            parse_mode="Markdown",
        )
        context.user_data["pending_meeting"] = {
            "title": title, "date": date, "time": time, "attendees": attendees
        }
        return

    # Double-check future time
    if start_time < datetime.now():
        await update.message.reply_text("⏰ You can’t schedule meetings in the past! Please choose a future time.")
        return

    # === Create Google Calendar event
    try:
        created = create_event(title, date, time, attendees=attendees)
    except Exception as e:
        print("Create event error:", e)
        await update.message.reply_text("⚠️ Failed to create the calendar event.")
        return

    if not created:
        await update.message.reply_text("⚠️ Event could not be created.")
        return

    event_link = created.get("htmlLink", "No link available")
    event_id = created.get("id")

    attendees_text = f"👥 Participants: {', '.join(attendees)}\n" if attendees else ""

    # === ✅ Enhanced interactive message
    msg = await update.message.reply_text(
        f"✅ *Meeting Scheduled!*\n\n"
        f"🗓 *{title}*\n"
        f"📅 {date} at {time}\n"
        f"{attendees_text}"
        f"🔗 [View in Calendar]({event_link})\n\n"
        f"✨ *You can reply to this message and say:*\n"
        f"• Change title to _Daily Sync_\n"
        f"• Reschedule meeting to _3pm tomorrow_\n"
        f"• Move meeting to _Friday_\n"
        f"• Cancel this meeting\n"
        f"• Add attendee _abc@gmail.com_",
        parse_mode="Markdown"
    )

    # === Store mapping for future replies
    event_map = context.application.bot_data.setdefault("event_map", {})
    event_map[msg.message_id] = event_id

    # Store last meeting per-user (optional)
    context.user_data["last_meeting"] = {
        "event_id": event_id,
        "message_id": msg.message_id,
        "title": title,
        "date": date,
        "time": time,
        "attendees": attendees,
    }

    print(f"[DEBUG] Stored event mapping: message_id={msg.message_id} -> event_id={event_id}")
