from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os, base64
from dotenv import load_dotenv
load_dotenv()
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def ensure_google_files_exist():
    """
    Decode base64-encoded credentials/token from environment variables
    (used on Render) and save them as JSON files.
    """
    cred_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
    token_b64 = os.getenv("GOOGLE_TOKEN_B64")

    if cred_b64 and not os.path.exists("credentials.json"):
        with open("credentials.json", "w") as f:
            f.write(base64.b64decode(cred_b64).decode("utf-8"))

    if token_b64 and not os.path.exists("token.json"):
        with open("token.json", "w") as f:
            f.write(base64.b64decode(token_b64).decode("utf-8"))


def get_calendar_service():
    """
    Returns an authenticated Google Calendar service.
    Works both locally and on Render (with env vars).
    """
    ensure_google_files_exist()

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        else:
            # For local dev only: interactive auth
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError("credentials.json not found!")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            with open("token.json", "w") as token:
                token.write(creds.to_json())

    service = build("calendar", "v3", credentials=creds)
    return service


def create_event(summary: str, start_time: datetime):
    service = get_calendar_service()
    end_time = start_time + timedelta(hours=1)

    event = {
        "summary": summary,
        "start": {"dateTime": start_time.isoformat(), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "Asia/Kolkata"},
    }

    event_result = service.events().insert(calendarId="primary", body=event).execute()
    return event_result


if __name__ == "__main__":
    print("🔍 Starting Google Calendar auth flow...")
    service = get_calendar_service()
    print("✅ Authenticated successfully!")

    event = create_event("Test Meeting", datetime.now() + timedelta(minutes=2))
    print(f"🎉 Created event: {event.get('htmlLink')}")
