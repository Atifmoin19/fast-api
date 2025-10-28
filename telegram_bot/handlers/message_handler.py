from telegram import Update
from telegram.ext import ContextTypes
from gemini_chat import interpret_command, parse_meeting_message
from google_calendar import (
    update_event_title,
    update_event_time,
    update_event_date,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I'm your Automation Bot.\n"
        "I can help you manage meetings and chat about topics.\n\n"
        "Try these:\n"
        "• /schedule meeting tomorrow at 10am with test@gmail.com\n"
        "• Reply to a meeting message and say 'Change title to Daily Sync'\n"
        "• Reply to a meeting message and say 'Reschedule to tomorrow at 3pm'\n"
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles:
    - Replies to meeting messages (update title/date/time)
    - Normal chat interpreted via Gemini
    """
    user_message = update.message.text.strip()

    # =====================================================
    # CASE A: User replied to a bot meeting message
    # =====================================================
    if update.message.reply_to_message:
        replied_id = update.message.reply_to_message.message_id
        event_map = context.application.bot_data.get("event_map", {})
        event_id = event_map.get(replied_id)

        if not event_id:
            await update.message.reply_text("⚠️ I couldn't find the meeting you're referring to.")
            return

        text_lower = user_message.lower()

        # --- Change Title ---
        if "change title" in text_lower or "change the title" in text_lower:
            new_title = text_lower
            new_title = (
                new_title.replace("change the title to", "")
                .replace("change title to", "")
                .replace("change title", "")
                .strip()
            )
            if new_title.startswith("to "):
                new_title = new_title[3:].strip()

            if not new_title:
                await update.message.reply_text("⚠️ Please specify the new title.")
                return

            try:
                updated = update_event_title(event_id, new_title)
            except TypeError:
                updated = update_event_title(new_title)
            except Exception as e:
                print("update_event_title error:", e)
                updated = None

            if updated:
                await update.message.reply_text(f"✅ Updated meeting title to *{new_title}*!", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Failed to update meeting title.")
            return

        # --- Reschedule / Change date/time ---
        if any(k in text_lower for k in ["reschedule", "change date", "change time", "move"]):
            parsed = parse_meeting_message(user_message)
            new_date = parsed.get("date")
            new_time = parsed.get("time")

            if not new_date and not new_time:
                await update.message.reply_text(
                    "⚠️ I couldn't detect a new date/time. Please specify like 'tomorrow at 10am'."
                )
                return

            updated = None
            try:
                if new_date and new_time:
                    updated = update_event_date(event_id, new_date, new_time)
                elif new_date:
                    updated = update_event_date(event_id, new_date)
                elif new_time:
                    updated = update_event_time(event_id, new_time)
            except TypeError:
                try:
                    if new_date and new_time:
                        updated = update_event_date(new_date, new_time)
                    elif new_date:
                        updated = update_event_date(new_date)
                    elif new_time:
                        updated = update_event_time(new_time)
                except Exception as e:
                    print("update date/time fallback error:", e)
                    updated = None
            except Exception as e:
                print("update date/time error:", e)
                updated = None

            if updated:
                pretty = f"{new_date or ''} {new_time or ''}".strip()
                await update.message.reply_text(f"✅ Meeting rescheduled to *{pretty}*!", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Failed to update meeting date/time.")
            return

        # Unknown action in reply
        await update.message.reply_text(
            "⚠️ I couldn't understand your instruction. Try 'Change title to ...' or 'Reschedule to ...'."
        )
        return

    # =====================================================
    # CASE B: Normal message (not a reply)
    # =====================================================
    ai_response = interpret_command(user_message)

    if isinstance(ai_response, dict):
        action = ai_response.get("action")

        # --- Update meeting title (non-reply) ---
        if action == "update_meeting_title":
            new_title = ai_response.get("new_title")
            if not new_title:
                await update.message.reply_text("⚠️ Please specify the new title.")
                return

            event_id = context.user_data.get("last_meeting", {}).get("event_id")
            updated = None
            try:
                if event_id:
                    updated = update_event_title(event_id, new_title)
                else:
                    updated = update_event_title(new_title)
            except TypeError:
                updated = update_event_title(new_title)
            except Exception as e:
                print("update_event_title error:", e)
                updated = None

            if updated:
                await update.message.reply_text(f"✅ Meeting title changed to *{new_title}*!", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Couldn't find a meeting to update.")
            return

        # --- Update meeting time (non-reply) ---
        if action == "update_meeting_time":
            new_time = ai_response.get("new_time")
            if not new_time:
                await update.message.reply_text("⚠️ Please specify the new time.")
                return

            event_id = context.user_data.get("last_meeting", {}).get("event_id")
            updated = None
            try:
                if event_id:
                    updated = update_event_time(event_id, new_time)
                else:
                    updated = update_event_time(new_time)
            except TypeError:
                updated = update_event_time(new_time)
            except Exception as e:
                print("update_event_time error:", e)
                updated = None

            if updated:
                await update.message.reply_text(f"✅ Meeting time updated to *{new_time}*!", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Couldn't find a meeting to update.")
            return

        # --- Update meeting date (non-reply) ---
        if action == "update_meeting_date":
            new_date = ai_response.get("new_date")
            if not new_date:
                await update.message.reply_text("⚠️ Please specify the new date (YYYY-MM-DD).")
                return

            event_id = context.user_data.get("last_meeting", {}).get("event_id")
            updated = None
            try:
                if event_id:
                    updated = update_event_date(event_id, new_date)
                else:
                    updated = update_event_date(new_date)
            except TypeError:
                updated = update_event_date(new_date)
            except Exception as e:
                print("update_event_date error:", e)
                updated = None

            if updated:
                await update.message.reply_text(f"✅ Meeting moved to *{new_date}*!", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Couldn't find a meeting to update.")
            return

        # --- Generic Gemini text reply ---
        reply_text = ai_response.get("reply")
        if reply_text:
            await update.message.reply_text(reply_text)
            return

    elif isinstance(ai_response, str):
        await update.message.reply_text(ai_response)
        return

    # fallback
    await update.message.reply_text("🤔 I'm not sure how to handle that yet.")
