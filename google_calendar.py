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


# ============================================================
# 🔐 GOOGLE AUTH HANDLING
# ============================================================
def ensure_google_files_exist():
    """
    Decode Google credentials/token from base64 env vars (for Render deployment)
    and save locally as credentials.json / token.json if missing.
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
    Return an authenticated Google Calendar API client.
    Works for both local (interactive) and Render-hosted environments.
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
                raise FileNotFoundError("credentials.json not found for local auth.")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            with open("token.json", "w") as token:
                token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


# ============================================================
# 📅 CREATE EVENT
# ============================================================
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
# 🔍 FIND LATEST UPCOMING EVENT
# ============================================================
def find_latest_event(service):
    """
    Return the most recent upcoming event (soonest future event).
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


# ============================================================
# ✏️ UPDATE EVENT TITLE
# ============================================================
def update_event_title(new_title: str):
    """
    Update the title of the most recent upcoming event.
    """
    service = get_calendar_service()
    event = find_latest_event(service)
    if not event:
        print("⚠️ No upcoming events found.")
        return None

    event["summary"] = new_title
    updated = service.events().update(
        calendarId="primary",
        eventId=event["id"],
        body=event,
        sendUpdates="all",
    ).execute()

    print(f"✅ Updated title to: {new_title}")
    return updated


# ============================================================
# ⏰ UPDATE EVENT TIME
# ============================================================
def update_event_time(new_time: str):
    """
    Change only the time of the latest event, keeping the same date.
    Expects 'new_time' in 'HH:MM' 24-hour format.
    """
    service = get_calendar_service()
    event = find_latest_event(service)
    if not event:
        print("⚠️ No upcoming events found.")
        return None

    try:
        # Extract current event date
        current_start = datetime.fromisoformat(event["start"]["dateTime"]).astimezone(IST)
        new_start = datetime.strptime(new_time, "%H:%M").replace(
            year=current_start.year,
            month=current_start.month,
            day=current_start.day,
            tzinfo=IST,
        )
    except ValueError:
        print(f"❌ Invalid time format: {new_time}")
        return None

    new_end = new_start + timedelta(hours=1)
    event["start"]["dateTime"] = new_start.isoformat()
    event["end"]["dateTime"] = new_end.isoformat()

    updated = service.events().update(
        calendarId="primary",
        eventId=event["id"],
        body=event,
        sendUpdates="all",
    ).execute()

    print(f"✅ Event time updated to: {new_time}")
    return updated


# ============================================================
# 📆 UPDATE EVENT DATE
# ============================================================
def update_event_date(new_date: str):
    """
    Change the date of the latest event while preserving time.
    Expects 'new_date' in 'YYYY-MM-DD' format.
    """
    service = get_calendar_service()
    event = find_latest_event(service)
    if not event:
        print("⚠️ No upcoming events found.")
        return None

    try:
        start = datetime.fromisoformat(event["start"]["dateTime"]).astimezone(IST)
        new_date_obj = datetime.strptime(new_date, "%Y-%m-%d").date()
        new_start = datetime.combine(new_date_obj, start.time(), tzinfo=IST)
    except ValueError:
        print(f"❌ Invalid date format: {new_date}")
        return None

    new_end = new_start + timedelta(hours=1)
    event["start"]["dateTime"] = new_start.isoformat()
    event["end"]["dateTime"] = new_end.isoformat()

    updated = service.events().update(
        calendarId="primary",
        eventId=event["id"],
        body=event,
        sendUpdates="all",
    ).execute()

    print(f"✅ Event moved to new date: {new_date}")
    return updated


# ============================================================
# 🧪 LOCAL TEST (for debugging)
# ============================================================
if __name__ == "__main__":
    print("Running google_calendar.py local test...")
    ensure_google_files_exist()
    svc = get_calendar_service()

    # Example tests
    # created = create_event("Demo Meeting", "2025-10-29", "10:00", ["test@gmail.com"])
    # print("✅ Created:", created.get("htmlLink"))

    updated = update_event_title("Daily Syncup (Test)")
    if updated:
        print("✅ Event title updated:", updated.get("htmlLink"))
    else:
        print("⚠️ No upcoming events found.")

    # update_event_time("22:00")
    # update_event_date("2025-10-30")
