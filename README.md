# Subcontractor Follow-Up Agent

An AI-powered automation agent that eliminates manual subcontractor follow-ups for construction project managers.

## What It Does

Automatically texts subcontractors every Monday at 8:00 AM asking for project updates. Claude AI generates a personalized message for each sub based on their trade, project, and last response — then Twilio sends the text and the Google Sheet gets updated automatically.

## The Problem It Solves

Having this issue myself, managing 15+ subcontractors across 5+ active job sites means constant manual follow-ups that are easy to forget. This agent replaces hours of weekly check-ins with a fully automated workflow.

## Tech Stack

- **Python** — core scripting
- **Anthropic Claude API** — generates personalized follow-up messages
- **Twilio** — sends SMS texts to subcontractors
- **Google Sheets API** — reads contact data, updates status after each text
- **OAuth2** — secure Google authentication

## How It Works

1. Reads subcontractor list from Google Sheets (name, phone, trade, project, status)
2. For each active sub, calls Claude API to generate a personalized text message
3. Sends the text via Twilio
4. Updates the sheet with last contact date and status
5. Runs automatically every Monday at 8:00 AM via Python scheduler

## Setup

1. Clone the repo
2. Install dependencies: `pip install anthropic twilio gspread google-auth google-auth-oauthlib schedule python-dotenv`
3. Create a `.env` file with your API credentials (see `.env.example`)
4. Add your Google OAuth credentials as `google_creds.json`
5. Run: `python sub_agent.py`

## Author

Greyson Ballard — [LinkedIn](https://linkedin.com/in/greysonballard)
