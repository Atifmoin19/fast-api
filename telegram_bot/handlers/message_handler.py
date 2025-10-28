from telegram import Update
from telegram.ext import ContextTypes
from gemini_chat import interpret_command
from google_calendar import (
    update_event_title,
    update_event_time,
    update_event_date,
    create_event,
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

    # =====================================================
    # 🧩 CASE 0: USER REPLIED TO A MEETING MESSAGE
    # =====================================================
    if update.message.reply_to_message:
        replied_id = update.message.reply_to_message.message_id
        event_mapping = context.bot_data.get("event_map", {})
        event_id = event_mapping.get(replied_id)

        if event_id:
            text_lower = user_message.lower()

            # --- Change title ---
            if "change title" in text_lower:
                new_title = (
                    text_lower.replace("change title", "")
                    .replace("to", "")
                    .strip()
                )
                if new_title:
                    success = update_event_title(event_id, new_title)
                    if success:
                        await update.message.reply_text(
                            f"✅ Updated meeting title to *{new_title}*!",
                            parse_mode="Markdown",
                        )
                    else:
                        await update.message.reply_text(
                            "⚠️ Failed to update meeting title."
                        )
                else:
                    await update.message.reply_text(
                        "⚠️ Please specify the new title."
                    )
                return

            # --- Change date ---
            if "change date" in text_lower or "reschedule" in text_lower:
                from gemini_chat import parse_meeting_message

                parsed = parse_meeting_message(user_message)
                new_date = parsed.get("date")
                new_time = parsed.get("time")

                if not new_date:
                    await update.message.reply_text(
                        "⚠️ Please specify a valid new date."
                    )
                    return

                success = update_event_date(event_id, new_date, new_time)
                if success:
                    await update.message.reply_text(
                        f"✅ Meeting rescheduled to *{new_date} {new_time or ''}*!",
                        parse_mode="Markdown",
                    )
                else:
                    await update.message.reply_text(
                        "⚠️ Failed to update meeting date/time."
                    )
                return

        # if reply message not mapped to any event
        await update.message.reply_text("⚠️ I couldn't find the meeting you're referring to.")
        return

    # =====================================================
    # 🧠 CASE 1: NORMAL MESSAGE (GEMINI INTERPRETATION)
    # =====================================================
    ai_response = interpret_command(user_message)

    if isinstance(ai_response, dict):
        action = ai_response.get("action")

        # ----------------------------
        # CASE 1: Schedule new meeting
        # ----------------------------
        if action == "schedule_meeting":
            details = ai_response.get("details", {})
            if not all(k in details for k in ["title", "date", "time"]):
                await update.message.reply_text(
                    "⚠️ Couldn't detect meeting date/time. Please specify clearly."
                )
                return

            created = create_event(
                title=details["title"],
                date=details["date"],
                time=details["time"],
                attendees=details.get("attendees"),
            )

            if created:
                msg = await update.message.reply_text(
                    f"✅ Meeting *{details['title']}* scheduled on {details['date']} at {details['time']}.\n"
                    f"[View in Calendar]({created.get('htmlLink')})",
                    parse_mode="Markdown",
                )

                # 🔗 Store mapping for reply-based updates
                context.bot_data.setdefault("event_map", {})[
                    msg.message_id
                ] = created.get("id")
                print(
                    f"[DEBUG] Stored event mapping: message_id={msg.message_id} -> event_id={created.get('id')}"
                )

            else:
                await update.message.reply_text("❌ Failed to schedule the meeting.")
            return

        # ----------------------------
        # CASE 2: Update title (no reply)
        # ----------------------------
        if action == "update_meeting_title":
            new_title = ai_response.get("new_title")
            if not new_title:
                await update.message.reply_text("⚠️ Please tell me the new title.")
                return

            updated = update_event_title(None, new_title)
            if updated:
                await update.message.reply_text(
                    f"✅ Meeting title changed to *{new_title}*!",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text("⚠️ No upcoming meeting found.")
            return

        # ----------------------------
        # CASE 3: Update time (no reply)
        # ----------------------------
        if action == "update_meeting_time":
            new_time = ai_response.get("new_time")
            if not new_time:
                await update.message.reply_text("⚠️ Please tell me the new time (e.g., 10:00).")
                return

            updated = update_event_time(None, new_time)
            if updated:
                await update.message.reply_text(
                    f"✅ Meeting time updated to *{new_time}*!",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text("⚠️ Couldn't find a meeting to update.")
            return

        # ----------------------------
        # CASE 4: Update date (no reply)
        # ----------------------------
        if action == "update_meeting_date":
            new_date = ai_response.get("new_date")
            if not new_date:
                await update.message.reply_text("⚠️ Please specify the new date (YYYY-MM-DD).")
                return

            updated = update_event_date(None, new_date)
            if updated:
                await update.message.reply_text(
                    f"✅ Meeting moved to *{new_date}*!",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text("⚠️ Couldn't find a meeting to update.")
            return

        # ----------------------------
        # CASE 5: General AI reply
        # ----------------------------
        reply_text = ai_response.get("reply")
        if reply_text:
            await update.message.reply_text(reply_text)
            return

    # ----------------------------
    # CASE 6: Plain text fallback
    # ----------------------------
    elif isinstance(ai_response, str):
        await update.message.reply_text(ai_response)
        return

    await update.message.reply_text("🤔 I'm not sure how to handle that yet.")
