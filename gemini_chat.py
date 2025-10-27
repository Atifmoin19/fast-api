from datetime import datetime
import os
import re
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()

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
    Example: "What is React?" or "Tell me a joke."
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip() if response.text else "🤔 I’m not sure how to respond to that."
    except Exception as e:
        print("Gemini error:", e)
        return "⚠️ Sorry, I couldn’t process that request right now."


# =====================================================
# STRUCTURED MEETING PARSER
# =====================================================


def parse_meeting_message(message: str) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""
    You are a meeting parser bot. Today's date is {today}.
    Extract meeting details (title, date, and time) from the following message.
    Always reply **only** in JSON format.

    Examples:
    - Input: "Schedule a meeting about project updates tomorrow at 10am"
      Output: {{"title": "Project Updates", "date": "2025-10-28", "time": "10:00"}}

    - Input: "Book a call on December 10 at 3 pm about UI review"
      Output: {{"title": "UI Review", "date": "2025-12-10", "time": "15:00"}}

    Message: "{message}"
    """

    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
        response = model.generate_content(prompt)
        text = response.text.strip()

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            return {
                "title": parsed.get("title", "Untitled"),
                "date": parsed.get("date"),
                "time": parsed.get("time"),
            }
        else:
            return {"title": "Untitled", "date": None, "time": None}

    except Exception as e:
        print("Gemini parse error:", e)
        return {"title": "Untitled", "date": None, "time": None}
