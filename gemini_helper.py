# gemini_helper.py
import google.generativeai as genai
import os
from datetime import datetime, timedelta
import re
from dotenv import load_dotenv
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-1.5-flash")

def parse_meeting_message(message: str):
    """
    Uses Gemini to interpret human-like text into structured meeting info.
    """
    prompt = f"""
    Extract structured meeting info from this message:
    "{message}"

    Return a JSON with keys:
    title (string),
    date (YYYY-MM-DD),
    time (HH:MM AM/PM),
    participants (list of names if mentioned),
    location (if any).

    If date or time not mentioned, set to null.
    """

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Try to find a JSON-like structure
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        import json
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {"title": None, "date": None, "time": None, "participants": [], "location": None}
