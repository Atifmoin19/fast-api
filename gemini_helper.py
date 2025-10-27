import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Configure Gemini with API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_available_model(preferred="gemini-1.5-flash", fallback="gemini-pro"):
    """
    Checks which model is supported on current SDK and returns best option.
    """
    try:
        models = [m.name for m in genai.list_models()]
        if any(preferred in m for m in models):
            print(f"✅ Using {preferred}")
            return preferred
        elif any(fallback in m for m in models):
            print(f"⚙️ Using fallback model: {fallback}")
            return fallback
        else:
            print("⚠️ No matching Gemini models found, defaulting to gemini-pro")
            return fallback
    except Exception as e:
        print(f"⚠️ Could not fetch model list: {e}")
        return fallback

# Automatically select model
MODEL_NAME = get_available_model()
model = genai.GenerativeModel(MODEL_NAME)

def parse_meeting_message(user_message: str):
    """
    Parses natural user input (like '/schedule a meeting tomorrow at 10 about budget')
    into structured date, time, and topic using Gemini.
    """
    prompt = f"""
    The user said: "{user_message}"

    Extract a meeting plan in JSON with these keys:
    - title (short meeting topic)
    - date (in YYYY-MM-DD)
    - time (24-hour format, HH:MM)

    If date or time is missing, guess from context (e.g. 'tomorrow' or 'next Monday').
    Only return valid JSON.
    """

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        print(f"Gemini response: {text}")
        return text
    except Exception as e:
        print(f"❌ Error while parsing meeting message: {e}")
        return '{"error": "Could not parse message"}'
