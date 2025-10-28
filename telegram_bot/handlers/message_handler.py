from telegram import Update
from telegram.ext import ContextTypes
from gemini_chat import interpret_command, parse_meeting_message
from google_calendar import (
    update_event_title,
    update_event_time,
    update_event_date,
    create_event,
)

# This handler handles:
# - Replies to a bot meeting message (uses message->event mapping stored in application.bot_data['event_map'])
#   to perform updates on the specific event.
# - General natural text commands (interpreted by Gemini via interpret_command).


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I'm your Automation Bot.\n"
        "I can help you schedule and manage meetings, and chat about tech topics.\n\n"
        "Try these:\n"
        "• /schedule meeting tomorrow at 10am with test@gmail.com\n"
        "• Reply to a meeting message and say 'Change title to Daily Sync'\n"
        "• Reply to a meeting message and say 'Reschedule to tomorrow at 3pm'\n"
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        # --- Change title (simple heuristic) ---
        if "change title" in text_lower or "change the title" in text_lower:
            # Extract possible new title using simple heuristics after keywords
            new_title = text_lower
            new_title = new_title.replace("change the title to", "").replace("change title to", "")
            new_title = new_title.replace("change title", "").strip()
            # fallback: if user wrote 'to <title>' keep after 'to'
            if new_title.startswith("to "):
                new_title = new_title[3:].strip()
            if not new_title:
                await update.message.reply_text("⚠️ Please specify the new title.")
                return

            # Try both flavors of calendar API (event_id-aware or not)
            try:
                updated = update_event_title(event_id, new_title)
            except TypeError:
                # function signature may be update_event_title(new_title)
                try:
                    updated = update_event_title(new_title)
                except Exception as e:
                    print("update_event_title error:", e)
                    updated = None
            except Exception as e:
                print("update_event_title error:", e)
                updated = None

            if updated:
                await update.message.reply_text(f"✅ Updated meeting title to *{new_title}*!", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Failed to update meeting title.")
            return

        # --- Reschedule / Change date/time ---
        if "reschedule" in text_lower or "change date" in text_lower or "change time" in text_lower or "move" in text_lower:
            # Use parse_meeting_message to extract new date / time from user's reply text
            parsed = parse_meeting_message(user_message)
            new_date = parsed.get("date")
            new_time = parsed.get("time")

            if not new_date and not new_time:
                await update.message.reply_text("⚠️ I couldn't detect a new date/time. Please specify like 'tomorrow at 10am' or '2025-10-30 15:00'.")
                return

            # Try update_event_date/event_time with event_id first, fallback to other signatures
            updated = None
            try:
                # If both date and time provided, prefer a combined date update function
                if new_date and new_time:
                    updated = update_event_date(event_id, new_date, new_time)
                elif new_date:
                    updated = update_event_date(event_id, new_date)
                elif new_time:
                    updated = update_event_time(event_id, new_time)
            except TypeError:
                # function signatures might not accept event_id; try alternate call patterns
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
                nice = f"{new_date or ''} {new_time or ''}".strip()
                await update.message.reply_text(f"✅ Meeting rescheduled to *{nice}*!", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Failed to update meeting date/time.")
            return

        # Unknown action in reply
        await update.message.reply_text("⚠️ I couldn't understand your instruction for this meeting. Try 'Change title to ...' or 'Reschedule to ...'.")
        return

    # =====================================================
    # CASE B: Normal non-reply messages => interpret via Gemini
    # =====================================================
    ai_response = interpret_command(user_message)

    if isinstance(ai_response, dict):
        action = ai_response.get("action")

        # Schedule a meeting (structured response from Gemini)
        if action == "schedule_meeting":
            details = ai_response.get("details", {})
            if not all(k in details for k in ("title", "date", "time")):
                await update.message.reply_text("⚠️ Couldn't detect meeting date/time. Please specify clearly.")
                return

            created = create_event(
                title=details["title"],
                date=details["date"],
                time=details["time"],
                attendees=details.get("attendees"),
            )

            if created:
                msg = (
                    f"✅ *Meeting Scheduled!*\n\n"
                    f"🗓 *{details['title']}*\n"
                    f"📅 {details['date']} at {details['time']}\n"
                )
                if details.get("attendees"):
                    msg += f"👥 Attendees: {', '.join(details['attendees'])}\n"
                msg += f"🔗 [View in Calendar]({created.get('htmlLink')})\n\n"
                msg += (
                    "✨ *You can also reply to this message and say:*\n"
                    "• Change meeting title to _Daily Sync_\n"
                    "• Reschedule meeting to _3pm tomorrow_\n"
                    "• Move meeting to _Friday_\n"
                    "• Cancel this meeting\n"
                    "• Add attendee _abc@gmail.com_\n"
                )

                sent = await update.message.reply_text(msg, parse_mode="Markdown")

                # store mapping for reply-based updates
                event_map = context.application.bot_data.setdefault("event_map", {})
                event_map[sent.message_id] = created.get("id")
                print(f"[DEBUG] Stored event mapping: message_id={sent.message_id} -> event_id={created.get('id')}")
            else:
                await update.message.reply_text("❌ Failed to schedule the meeting.")
            return

        # Update title by plain command (not reply) — try to update the latest/upcoming
        if action == "update_meeting_title":
            new_title = ai_response.get("new_title")
            if not new_title:
                await update.message.reply_text("⚠️ Please tell me the new title.")
                return
            # Try to update by event id if last_meeting stored
            event_id = context.user_data.get("last_meeting", {}).get("event_id")
            updated = None
            try:
                if event_id:
                    updated = update_event_title(event_id, new_title)
                else:
                    updated = update_event_title(new_title)
            except TypeError:
                # fallback signature
                try:
                    updated = update_event_title(new_title)
                except Exception as e:
                    print("update_event_title fallback error:", e)
                    updated = None
            except Exception as e:
                print("update_event_title error:", e)
                updated = None

            if updated:
                await update.message.reply_text(f"✅ Meeting title changed to *{new_title}*!", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ No upcoming meeting found to update.")
            return

        # Update time by plain command (not reply)
        if action == "update_meeting_time":
            new_time = ai_response.get("new_time")
            if not new_time:
                await update.message.reply_text("⚠️ Please tell me the new time (e.g., 10:00).")
                return
            event_id = context.user_data.get("last_meeting", {}).get("event_id")
            updated = None
            try:
                if event_id:
                    updated = update_event_time(event_id, new_time)
                else:
                    updated = update_event_time(new_time)
            except TypeError:
                try:
                    updated = update_event_time(new_time)
                except Exception as e:
                    print("update_event_time fallback error:", e)
                    updated = None
            except Exception as e:
                print("update_event_time error:", e)
                updated = None

            if updated:
                await update.message.reply_text(f"✅ Meeting time updated to *{new_time}*!", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Couldn't find a meeting to update.")
            return

        # Update date by plain command (not reply)
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
                try:
                    updated = update_event_date(new_date)
                except Exception as e:
                    print("update_event_date fallback error:", e)
                    updated = None
            except Exception as e:
                print("update_event_date error:", e)
                updated = None

            if updated:
                await update.message.reply_text(f"✅ Meeting moved to *{new_date}*!", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Couldn't find a meeting to update.")
            return

        # Generic AI reply
        reply_text = ai_response.get("reply")
        if reply_text:
            await update.message.reply_text(reply_text)
            return

    # If interpret_command returned plain string
    elif isinstance(ai_response, str):
        await update.message.reply_text(ai_response)
        return

    # fallback
    await update.message.reply_text("🤔 I'm not sure how to handle that yet.")
