
from dotenv import load_dotenv
load_dotenv()
"""
Subcontractor Follow-Up Agent
------------------------------
Reads subcontractor data from Google Sheets, uses Claude to generate
personalized follow-up texts, sends them via Twilio, and updates the sheet.
Runs automatically every Monday at 8:00 AM.

SETUP:
1. pip install anthropic twilio gspread google-auth google-auth-oauthlib schedule
2. Fill in your credentials in the CONFIG section below
3. Place your downloaded OAuth JSON file in the same folder, renamed to google_creds.json
4. Run: python sub_agent.py
   - First run will open a browser to log in with Google — click Allow
   - After that it saves a token and never asks again
"""

import anthropic
import gspread
import schedule
import time
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime
from twilio.rest import Client
import os
import pickle

ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY")
TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

GOOGLE_SHEET_ID     = "1Vix4dMnkiQNmZa_S6HEZlOwP03sYZIFkDFPOfjFEDNk"
GOOGLE_CREDS_FILE   = "google_creds.json"   # Your downloaded OAuth JSON
GOOGLE_TOKEN_FILE   = "token.pickle"        # Auto-created after first login

YOUR_NAME           = "Greyson"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ─────────────────────────────────────────────
# GOOGLE SHEETS CONNECTION (OAuth2)
# ─────────────────────────────────────────────

def get_google_credentials():
    """Get or refresh Google OAuth2 credentials."""
    creds = None

    # Load saved token if it exists
    if os.path.exists(GOOGLE_TOKEN_FILE):
        with open(GOOGLE_TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    # If no valid credentials, log in via browser
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next run
        with open(GOOGLE_TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return creds

def connect_to_sheet():
    """Connect to the Google Sheet."""
    creds = get_google_credentials()
    client = gspread.authorize(creds)
    sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
    return sheet

def get_subcontractors(sheet):
    """Pull all rows from the sheet as a list of dicts."""
    return sheet.get_all_records()

def update_last_contact(sheet, row_index, date_str):
    """Update the Last Contact Date column (col 5) for a given row."""
    sheet.update_cell(row_index + 2, 5, date_str)

def update_status(sheet, row_index, status):
    """Update the Status column (col 7) for a given row."""
    sheet.update_cell(row_index + 2, 7, status)

# ─────────────────────────────────────────────
# CLAUDE — GENERATE FOLLOW-UP MESSAGE
# ─────────────────────────────────────────────

def generate_followup_text(sub: dict) -> str:
    """Use Claude to write a personalized follow-up text for the sub."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""
You are helping a construction project manager named {YOUR_NAME} follow up with subcontractors via text message.

Write a SHORT, professional, friendly follow-up text (2-3 sentences max) to this subcontractor:
- Name: {sub['Contractor Name']}
- Trade: {sub['Trade']}
- Project: {sub['Current Project']}
- Last Response: {sub.get('Last Response') or 'No response yet'}
- Status: {sub.get('Status') or 'Unknown'}
- Notes: {sub.get('Notes') or 'None'}

The text should:
- Be casual but professional
- Ask for a status update on their work
- Reference the specific project
- Sign off as {YOUR_NAME}
- NOT be pushy or aggressive
- Be under 160 characters if possible

Return ONLY the text message, nothing else.
"""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text.strip()

# ─────────────────────────────────────────────
# TWILIO — SEND TEXT
# ─────────────────────────────────────────────

def send_text(to_number: str, message_body: str):
    """Send a text via Twilio."""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    # Clean up phone number format
    clean_number = "".join(filter(str.isdigit, to_number))
    if not clean_number.startswith("1"):
        clean_number = "1" + clean_number
    formatted = f"+{clean_number}"

    msg = client.messages.create(
        body=message_body,
        from_=TWILIO_PHONE_NUMBER,
        to=formatted
    )
    return msg.sid

# ─────────────────────────────────────────────
# MAIN AGENT LOGIC
# ─────────────────────────────────────────────

def run_followup_agent():
    print(f"\n🔄 Running subcontractor follow-up agent — {datetime.now().strftime('%A %B %d, %Y at %I:%M %p')}")

    try:
        sheet = connect_to_sheet()
        subs  = get_subcontractors(sheet)

        if not subs:
            print("No subcontractors found in sheet.")
            return

        sent_count    = 0
        skipped_count = 0

        for i, sub in enumerate(subs):
            name  = sub.get("Contractor Name", "").strip()
            phone = sub.get("Phone Number",    "").strip()

            # Skip empty rows
            if not name or not phone:
                continue

            # Skip subs marked complete
            if sub.get("Status", "").lower() in ["complete", "done", "closed"]:
                print(f"  ⏭️  Skipping {name} — marked as {sub['Status']}")
                skipped_count += 1
                continue

            print(f"  📱 Generating text for {name} ({sub.get('Trade','')}) — {sub.get('Current Project','')}...")

            message = generate_followup_text(sub)
            print(f"     Message: {message}")

            sid = send_text(phone, message)
            print(f"     ✅ Sent! SID: {sid}")

            today = datetime.now().strftime("%m/%d/%Y")
            update_last_contact(sheet, i, today)
            update_status(sheet, i, "Contacted")

            sent_count += 1
            time.sleep(1)   # Small delay between texts

        print(f"\n✅ Done. Sent {sent_count} texts, skipped {skipped_count}.")

    except Exception as e:
        print(f"❌ Error: {e}")

# ─────────────────────────────────────────────
# SCHEDULER — EVERY MONDAY AT 8:00 AM
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 Subcontractor Follow-Up Agent started.")
    print("   Scheduled to run every Monday at 8:00 AM.")
    print("   Press Ctrl+C to stop.\n")

    # Schedule for every Monday at 8am
    schedule.every().monday.at("08:00").do(run_followup_agent)

    # ── Uncomment the line below to test immediately ──
    run_followup_agent()

    while True:
        schedule.run_pending()
        time.sleep(60)
