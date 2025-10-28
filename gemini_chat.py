from datetime import datetime, timedelta
import os
import re
import json
from dotenv import load_dotenv
from google import genai
from zoneinfo import ZoneInfo

# Import your Google Calendar event creator
from google_calendar import create_event

load_dotenv()

# =====================================================
# CONFIG
# =====================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ Missing GEMINI_API_KEY in environment variables!")

client = genai.Client(api_key=GEMINI_API_KEY)
IST = ZoneInfo("Asia/Kolkata")

# =====================================================
# HELPERS
# =====================================================
def get_ist_time() -> datetime:
    return datetime.now(IST)


# =====================================================
# GENERIC CHAT
# =====================================================
def get_gemini_reply(prompt: str) -> str:
    """General-purpose Gemini text generation with context of current IST time."""
    try:
        now = get_ist_time()
        today_str = now.strftime("%B %d, %Y")
        time_str = now.strftime("%I:%M %p")
        full_prompt = (
            f"Today’s date is {today_str} and current time is {time_str} IST. "
            f"You are a helpful assistant. Respond naturally.\n\nUser query: {prompt}"
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt
        )

        return response.text.strip() if response.text else "🤔 I’m not sure how to respond."
    except Exception as e:
        print("Gemini error:", e)
        return "⚠️ Sorry, I couldn’t process that request right now."


# =====================================================
# MEETING PARSER
# =====================================================
def parse_meeting_message(message: str) -> dict:
    """
    Extract meeting details (title, date, time, attendees) from a natural sentence using Gemini.
    Adjusts if the meeting is in the past (bumps to next day).
    """
    prompt = f"""
You are a meeting extraction assistant.
Extract the following fields from the user's message:
- title: The meeting title
- date: The meeting date in YYYY-MM-DD format
- time: The meeting start time in 24-hour format HH:MM
- attendees: A list of participant emails or names if possible

If any field is missing or unclear, set it to null.
Always reply in valid JSON.

Example:
Input: "Schedule a sync with atif@gmail.com and moon tomorrow at 10 am"
Output: {{
  "title": "Sync",
  "date": "2025-10-28",
  "time": "10:00",
  "attendees": ["atif@gmail.com", "moon"]
}}

Now extract details from this message:
"{message}"
"""

    try:
        now = get_ist_time()
        full_prompt = (
            f"Today's date is {now.strftime('%B %d, %Y')} and current time is {now.strftime('%I:%M %p')} IST.\n"
            f"{prompt}"
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt
        )
        text = response.text.strip()

        # Extract JSON safely
        match = re.search(r"\{.*\}", text, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else {}

        title = parsed.get("title", "Untitled Meeting")
        date_str = parsed.get("date")
        time_str = parsed.get("time")
        attendees = parsed.get("attendees", []) or []

        # Normalize attendees (strip + remove blanks)
        attendees = [a.strip() for a in attendees if isinstance(a, str) and a.strip()]

        # Validate and adjust for past
        past = False
        if date_str and time_str:
            try:
                meeting_dt = datetime.strptime(
                    f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=IST)
                now_ist = get_ist_time()
                if meeting_dt < now_ist:
                    past = True
                    meeting_dt += timedelta(days=1)
                    date_str = meeting_dt.strftime("%Y-%m-%d")
                    time_str = meeting_dt.strftime("%H:%M")
                    print("⚠️ Adjusted meeting to future date/time")
            except ValueError:
                pass

        return {
            "title": title,
            "date": date_str,
            "time": time_str,
            "attendees": attendees,
            "past": past,
        }

    except Exception as e:
        print("Gemini parse error:", e)
        return {
            "title": "Untitled",
            "date": None,
            "time": None,
            "attendees": [],
            "past": False,
        }


# =====================================================
# INTERPRETER FUNCTION
# =====================================================
def interpret_command(command: str) -> str:
    """
    Interpret a natural language command.  
    If it's a meeting request → create a Google Calendar event.  
    Otherwise → use Gemini to reply conversationally.
    """
    command_lower = command.lower()

    # Detect meeting creation intent
    if any(word in command_lower for word in ["schedule", "meeting", "call", "event", "calendar", "appointment"]):
        details = parse_meeting_message(command)
        if not details.get("date") or not details.get("time"):
            return "⚠️ Couldn’t detect meeting date/time. Please specify clearly."

        try:
            created = create_event(
                title=details["title"],
                date=details["date"],
                time=details["time"],
                attendees=details["attendees"]
            )
            link = created.get("htmlLink", "(no link)")
            return f"✅ Meeting '{details['title']}' scheduled on {details['date']} at {details['time']}.\n🔗 {link}"
        except Exception as e:
            print("Calendar error:", e)
            return f"⚠️ Failed to schedule event: {e}"

    # Default fallback → Gemini response
    return get_gemini_reply(command)


# =====================================================
# GEMINI SETUP
# =====================================================
def setup_gemini():
    """
    Initializes Gemini client to ensure the API key is loaded properly.
    Called once from main.py during FastAPI startup.
    """
    try:
        if not GEMINI_API_KEY:
            raise ValueError("❌ Missing GEMINI_API_KEY in environment variables!")
        _ = client.models.list()  # Light check to confirm API key works
        print("✅ Gemini API initialized successfully!")
    except Exception as e:
        print("⚠️ Gemini setup failed:", e)
