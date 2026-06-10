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

# הגדרת הרשאות מדויקות (Scopes)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar"
]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

def get_credentials() -> Credentials:
    """מנגנון התחברות וחידוש טוקנים מול גוגל"""
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
    """סריקת אימיילים חכמה מהיומיים האחרונים"""
    two_days_ago = (datetime.now() - timedelta(days=2)).strftime('%Y/%m/%d')
    query = f"after:{two_days_ago} (פגישה OR זימון OR meeting)"
    
    result = gmail_service.users().messages().list(userId='me', q=query).execute()
    messages = result.get('messages', [])
    
    print(f"📬 נמצאו {len(messages)} הודעות רלוונטיות לפגישה בתיבה.")
    
    email_list = []
    for msg in messages:
        txt = gmail_service.users().messages().get(userId='me', id=msg['id'], format='raw').execute()
        msg_bytes = base64.urlsafe_b64decode(txt['raw'].encode('ASCII'))
        email_list.append({"id": msg['id'], "content": msg_bytes.decode('utf-8', errors='ignore')})
    return email_list

def analyze_email_with_llm(email_content: str) -> dict | None:
+ +
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
    """בדיקת זמינות בלוח השנה"""
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
    """יצירת אירוע ביומן"""
    start_time = datetime.strptime(f"{meeting_info['date']} {meeting_info['time']}", "%Y-%m-%d %H:%M")
    end_time = start_time + timedelta(hours=meeting_info['duration_hours'])
    
    event = {
        'summary': meeting_info['title'],
        'location': meeting_info['location'],
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Asia/Jerusalem'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Asia/Jerusalem'},
    }
    calendar_service.events().insert(calendarId='primary', body=event).execute()
    print(f"🎉 אירוע נקבע בהצלחה בלוח השנה: {meeting_info['title']}")

def send_rejection_email(gmail_service, recipient: str):
    """שליחת מייל דחייה קשיח"""
    msg = EmailMessage()
    msg["To"] = recipient
    msg["Subject"] = "עדכון לגבי זימון הפגישה"
    msg.set_content("לא ניתן לבצע את הפגישה")
    
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    gmail_service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
    print(f"✉️ נשלח מייל דחייה לכתובת: {recipient}")

def main():
    creds = get_credentials()
    gmail_service = build("gmail", "v1", credentials=creds)
    calendar_service = build("calendar", "v3", credentials=creds)
    
    # 🔍 בדיקת החשבון המחובר האמיתי:
    try:
        primary_cal = calendar_service.calendars().get(calendarId='primary').execute()
        print(f"📧 [אבחון] הסוכן מחובר כרגע לחשבון גוגל: {primary_cal['id']}")
    except Exception:
        print("📧 [אבחון] לא הצלחתי לשלוף את כתובת המייל, ממשיך כרגיל...")
    
    print("🤖 סוכן ה-AI מתחיל בסריקת הודעות...")
    emails = fetch_recent_emails(gmail_service)
    
    if not emails:
        print("🤷 אין הודעות רלוונטיות בתיבה מהיומיים האחרונים.")
        return

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
                break 
            else:
                send_rejection_email(gmail_service, meeting_info["sender"])

if __name__ == "__main__":
    main()