from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os, base64, json
from dotenv import load_dotenv

load_dotenv()
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
IST = ZoneInfo("Asia/Kolkata")


def ensure_google_files_exist():
    """
    If you store credentials/token base64 in env (for Render),
    decode them and save as credentials.json / token.json.
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
    Works both locally (interactive auth) and on Render (env-provided files).
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
            # Local interactive auth only
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError("credentials.json not found (for local auth).")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            with open("token.json", "w") as token:
                token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def create_event(title: str, date: str, time: str, attendees: list[str] | None = None):
    """
    Create a Google Calendar event with optional attendees.

    - title: Event title
    - date: ISO date 'YYYY-MM-DD'
    - time: 24-hour 'HH:MM'
    - attendees: optional list of email strings

    Returns: dict (Google event object) or raises Exception on failure.
    """
    service = get_calendar_service()

    try:
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=IST)
    except ValueError as e:
        raise ValueError(f"Invalid date/time format: {date} {time}") from e

    end_dt = start_dt + timedelta(hours=1)

    event = {
        "summary": title,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Kolkata"},
    }

    if attendees:
        event["attendees"] = [{"email": email} for email in attendees]

    created = service.events().insert(calendarId="primary", body=event, sendUpdates="all").execute()
    return created


# ============================================================
# 🆕 UPDATE / MODIFY EXISTING MEETINGS
# ============================================================

def find_latest_event(service):
    """
    Helper: Find the most recently created/upcoming event on the primary calendar.
    """
    now = datetime.now(IST).isoformat()
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=1,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])
    return events[0] if events else None


def update_event_title(new_title: str):
    """
    Update the most recent (upcoming) event's title.
    """
    service = get_calendar_service()
    event = find_latest_event(service)
    if not event:
        return None

    event["summary"] = new_title
    updated = service.events().update(
        calendarId="primary",
        eventId=event["id"],
        body=event,
        sendUpdates="all",
    ).execute()

    return updated


# ============================================================
# LOCAL TEST
# ============================================================
if __name__ == "__main__":
    print("Running google_calendar.py local test...")
    ensure_google_files_exist()
    svc = get_calendar_service()

    # Uncomment below lines for quick checks
    # ev = create_event("Local Test", datetime.now().strftime("%Y-%m-%d"), (datetime.now() + timedelta(minutes=5)).strftime("%H:%M"))
    # print("Event created:", ev.get("htmlLink"))

    updated = update_event_title("Daily Syncup (Test)")
    if updated:
        print("✅ Event updated:", updated.get("htmlLink"))
    else:
        print("⚠️ No upcoming events found.")
