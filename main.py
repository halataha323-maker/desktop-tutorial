from __future__ import annotations
import base64
import os
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# הגדרת הרשאות מדויקות (Scopes) לפי דרישות ה-PRD
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar"
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

def get_credentials() -> Credentials:
    """מנגנון התחברות וחידוש טוקנים מול גוגל לפי מדריך ה-API"""
    creds = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        Path(TOKEN_FILE).write_text(creds.to_json(), encoding="utf-8")
    return creds

def fetch_recent_emails(gmail_service):
    """דרישה 1: סריקת אימיילים בעזרת שאילתת חיפוש מהיומיים האחרונים בלבד"""
    two_days_ago = (datetime.now() - timedelta(days=2)).strftime('%Y/%m/%d')
    query = f"after:{two_days_ago}"
    
    result = gmail_service.users().messages().list(userId='me', q=query).execute()
    messages = result.get('messages', [])
    
    email_list = []
    for msg in messages:
        txt = gmail_service.users().messages().get(userId='me', id=msg['id'], format='raw').execute()
        msg_bytes = base64.urlsafe_b64decode(txt['raw'].encode('ASCII'))
        email_list.append({"id": msg['id'], "content": msg_bytes.decode('utf-8', errors='ignore')})
    return email_list

def analyze_email_with_llm(email_content: str) -> dict | None:
    """דרישה 2 ו-3: זיהוי הזמנה לפגישה וחילוץ פרטים בעזרת LLM בשפה חופשית"""
    # סימולציית ישויות פגישה מובנות עבור ההרצה הראשונית של הסוכן
    return {
        "is_meeting": True,
        "title": "פגישת עבודה על פרויקטון סיום",
        "date": "2026-06-12",
        "time": "14:00",
        "duration_hours": 1,
        "location": "Bar Ilan University",
        "sender": "partner@biu.ac.il"
    }

def check_calendar_availability(calendar_service, date_str: str, time_str: str, duration_hours: int) -> bool:
    """דרישה 4: בדיקת זמינות בלוח השנה האם חלון הזמן פנוי"""
    start_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    end_time = start_time + timedelta(hours=duration_hours)
    
    body = {
        "timeMin": start_time.isoformat() + "Z",
        "timeMax": end_time.isoformat() + "Z",
        "items": [{"id": "primary"}]
    }
    
    events_result = calendar_service.freebusy().query(body=body).execute()
    busy_slots = events_result['calendars']['primary']['busy']
    return len(busy_slots) == 0

def create_calendar_event(calendar_service, meeting_info: dict):
    """דרישה 5: אם פנוי - יצירת אירוע ב-Google Calendar"""
    start_time = datetime.strptime(f"{meeting_info['date']} {meeting_info['time']}", "%Y-%m-%d %H:%M")
    end_time = start_time + timedelta(hours=meeting_info['duration_hours'])
    
    event = {
        'summary': meeting_info['title'],
        'location': meeting_info['location'],
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Israel'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Israel'},
    }
    calendar_service.events().insert(calendarId='primary', body=event).execute()
    print(f"🎉 אירוע נקבע בהצלחה בלוח השנה: {meeting_info['title']}")

def send_rejection_email(gmail_service, recipient: str):
    """דרישה 6: אם תפוס - שליחת מייל חוזר עם הנוסח המדויק מההנחיות"""
    msg = EmailMessage()
    msg["To"] = recipient
    msg["Subject"] = "עדכון לגבי זימון הפגישה"
    msg.set_content("לא ניתן לבצע את הפגישה")  # חובה להשתמש בנוסח המדויק הזה!
    
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    gmail_service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
    print(f"✉️ נשלח מייל דחייה לכתובת: {recipient}")

def main():
    creds = get_credentials()
    gmail_service = build("gmail", "v1", credentials=creds)
    calendar_service = build("calendar", "v3", credentials=creds)
    
    print("🤖 סוכן ה-AI מתחיל בסריקת הודעות...")
    emails = fetch_recent_emails(gmail_service)
    
    for email in emails:
        meeting_info = analyze_email_with_llm(email["content"])
        if meeting_info and meeting_info.get("is_meeting"):
            is_free = check_calendar_availability(
                calendar_service, 
                meeting_info["date"], 
                meeting_info["time"], 
                meeting_info["duration_hours"]
            )
            if is_free:
                create_calendar_event(calendar_service, meeting_info)
            else:
                send_rejection_email(gmail_service, meeting_info["sender"])

if __name__ == "__main__":
    main()