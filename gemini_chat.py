# gemini_chat.py
import os
from dotenv import load_dotenv
import google.generativeai as genai
load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_gemini_reply(prompt: str) -> str:
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip() if response and response.text else "I'm not sure how to respond to that."
    except Exception as e:
        print("Gemini error:", e)
        return "Sorry, I couldn't process that request right now."
