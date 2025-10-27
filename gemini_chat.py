from datetime import datetime, timedelta
import os
import re
import json
from dotenv import load_dotenv
from google import genai
from zoneinfo import ZoneInfo

load_dotenv()



def get_ist_time():
    return datetime.now(ZoneInfo("Asia/Kolkata"))

# =====================================================
# CONFIGURATION
# =====================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ Missing GEMINI_API_KEY in environment variables!")

client = genai.Client(api_key=GEMINI_API_KEY)

# =====================================================
# GENERIC CHAT REPLY
# =====================================================
def get_gemini_reply(prompt: str) -> str:
    """
    Get a natural language response for any user query.
    Includes real-time context (today's date/time).
    """
    try:
        now = get_ist_time()
        today_str = now.strftime("%B %d, %Y")
        time_str = now.strftime("%I:%M %p")
        full_prompt = (
            f"Today’s date is {today_str} and current time is {time_str} IST."
            f"You are an AI assistant that responds naturally to the user. "
            f"User query: {prompt}"
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt
        )
        return response.text.strip() if response.text else "🤔 I’m not sure how to respond to that."
    except Exception as e:
        print("Gemini error:", e)
        return "⚠️ Sorry, I couldn’t process that request right now."


# =====================================================
# STRUCTURED MEETING PARSER
# =====================================================


def parse_meeting_message(message: str) -> dict:
    """
    Extract meeting details (title, date, time) from a natural sentence using Gemini.
    Disallows meetings scheduled in the past.
    """

    prompt = f"""
You are a meeting extraction assistant.
Extract the meeting title, date (YYYY-MM-DD), and time (24-hour format: HH:MM)
from the user message.

If time or date are missing or ambiguous, leave them null.

Always reply in strict JSON only.
Example:
Input: "Book a syncup tomorrow at 10 am"
Output: {{"title": "Syncup", "date": "2025-10-28", "time": "10:00"}}

Now extract from this message:
"{message}"
"""

    try:
        now = get_ist_time()
        today_str = now.strftime("%B %d, %Y")
        time_str = now.strftime("%I:%M %p")
        full_prompt = (
            f"Today’s date is {today_str} and current time is {time_str} IST."
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

        # 🕒 Validate and combine date/time
        if date_str and time_str:
            try:
                meeting_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                now = datetime.now()

                # 🚫 Disallow past meetings
                if meeting_dt < now:
                    # Auto-bump to next day, same time
                    meeting_dt = meeting_dt + timedelta(days=1)
                    date_str = meeting_dt.strftime("%Y-%m-%d")
                    time_str = meeting_dt.strftime("%H:%M")
                    print("⚠️ Adjusted meeting to future date/time")

            except ValueError:
                pass  # Invalid date/time format; handled below

        return {
            "title": title,
            "date": date_str,
            "time": time_str,
        }

    except Exception as e:
        print("Gemini parse error:", e)
        return {"title": "Untitled", "date": None, "time": None}