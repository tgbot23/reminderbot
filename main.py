import os
import json
import threading
import time
from datetime import datetime, timedelta # Import timedelta for time window
from dateutil import parser
import pytz
import schedule
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request

# --- Configuration & Setup ---

# Bot token and timezone
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    # Raise an exception if TOKEN is not set, Render will log this
    raise ValueError("BOT_TOKEN environment variable not set. Please set it on Render.")

bot = telebot.TeleBot(TOKEN)
IST = pytz.timezone("Asia/Kolkata")
app = Flask(__name__)

# --- Google Sheets Functions ---

def get_google_sheet():
    """Authorizes with Google Sheets and returns the sheet object."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Load credentials from environment variable
    creds_json_str = os.environ.get("GOOGLE_CREDS_JSON")
    if not creds_json_str:
        raise ValueError("GOOGLE_CREDS_JSON environment variable not set. Please set it on Render.")
    
    try:
        creds_json = json.loads(creds_json_str)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Telegram Reminders").sheet1
        return sheet
    except Exception as e:
        print(f"❌ Error setting up Google Sheet: {e}")
        print("Please ensure GOOGLE_CREDS_JSON is correctly formatted and the service account has access.")
        raise # Re-raise to stop the application if sheet access fails

def add_to_google_sheet(chat_id, type_, name, date, time_):
    """Adds a new reminder to the Google Sheet."""
    try:
        sheet = get_google_sheet()
        sheet.append_row([str(chat_id), type_, name, date, time_])
        print(f"✅ Added reminder to Google Sheet: {name}, {date}, {time_}")
    except Exception as e:
        print(f"❌ Error adding to Google Sheet: {e}")

# --- Reminder Sending Logic ---

def send_reminders():
    """Checks Google Sheet for reminders and sends them."""
    print(f"Checking for reminders at {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        now = datetime.now(IST)
        today = now.strftime("%d-%m") # e.g., "14-07"

        sheet = get_google_sheet()
        records = sheet.get_all_records()

        for entry in records:
            entry_date = entry.get("date", "")
            entry_time_str = entry.get("time", "") # e.g., "08:00"

            # Check if the date matches today
            if entry_date.startswith(today): # Using startswith to match "DD-MM" part
                try:
                    # Parse the reminder time from sheet
                    reminder_time_obj = datetime.strptime(entry_time_str, "%H:%M").time()
                    
                    # Combine today's date with reminder's time for comparison
                    reminder_datetime = datetime.combine(now.date(), reminder_time_obj).replace(tzinfo=IST)

                    # Calculate time difference
                    # Check if the current time is within a 2-minute window of the reminder time
                    # This helps account for minor scheduling delays
                    time_difference = abs((now - reminder_datetime).total_seconds())

                    # If current time is past the reminder time AND within the window
                    # OR current time is exactly the reminder time
                    if time_difference < 120: # Within 120 seconds (2 minutes)
                        years = now.year - int(entry_date[-4:]) # Get year difference
                        
                        msg = ""
                        if entry["type"] == "Birthday":
                            msg = f"🎂 Aaj {entry['name']} ka Birthday hai! {years} saal ke ho gaye hain. Mubarak ho!"
                        else: # Anniversary
                            msg = f"💍 Aaj {entry['name']} ki shaadi ki {years}vi anniversary hai! Mubarak ho!"
                        
                        try:
                            # Send message
                            bot.send_message(int(entry["chat_id"]), msg)
                            print(f"✅ Reminder sent to {entry['name']} (chat_id: {entry['chat_id']}) for {entry_date} at {entry_time_str}")
                            
                            # Optional: Remove reminder after sending (if it's a one-time thing)
                            # Or mark it as sent to prevent re-sending for the same day
                            # For annual reminders, you typically don't remove.
                            
                        except Exception as e:
                            print(f"❌ Error sending reminder to {entry['chat_id']}: {e}")
                            # This could be due to invalid chat_id, bot blocked, etc.
                    else:
                        # print(f"Skipping reminder for {entry['name']}: not within active window. Diff: {time_difference:.2f}s")
                        pass

                except ValueError as ve:
                    print(f"❌ Invalid time format '{entry_time_str}' for {entry_date} in sheet. Error: {ve}")
                except Exception as ce:
                    print(f"❌ Critical error processing entry for {entry['name']}: {ce}")

    except Exception as e:
        print(f"❌ Error in send_reminders(): {e}")

# IMPORTANT: Define schedule_checker BEFORE it's called by threading.Thread
def schedule_checker():
    """Runs the schedule continuously in a background thread."""
    print("Scheduling reminder checks every minute...")
    schedule.every().minute.do(send_reminders) # Schedule send_reminders to run every minute
    while True:
        schedule.run_pending()
        time.sleep(1) # Sleep for 1 second to not consume too much CPU

# --- User State Management for Conversation ---

user_state = {} # Stores conversation state for each chat_id

# --- Telegram Handlers ---

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Namaste! Kis cheez ka reminder chahiye?\n1. Birthday\n2. Anniversary")
    user_state[message.chat.id] = {} # Initialize state for new conversation

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    chat_id = message.chat.id
    text = message.text.strip()
    state = user_state.get(chat_id, {})

    if not state: # If no active state, it's a new conversation or invalid input
        if text in ["1", "2"]:
            user_state[chat_id] = {"type": "Birthday" if text == "1" else "Anniversary"}
            bot.reply_to(message, "Naam bataiye (jiska reminder chahiye):")
        else:
            bot.reply_to(message, "Pehle choose karein:\n1. Birthday\n2. Anniversary")
            # Clear state if user types something unexpected at start
            user_state.pop(chat_id, None)
    elif "type" in state and "name" not in state:
        user_state[chat_id]["name"] = text
        bot.reply_to(message, "Date bataiye Birthday/Shaadi ki (jaise: 01-01-2000 ya 1 Jan 2000):")
    elif "name" in state and "date" not in state:
        try:
            # Use dateutil.parser for flexible date parsing
            dob = parser.parse(text, dayfirst=True).date()
            user_state[chat_id]["date"] = dob.strftime("%d-%m-%Y")
            bot.reply_to(message, "Kitne baje reminder chahiye? (jaise: 08:00 AM ya 07:30 PM)")
        except Exception:
            bot.reply_to(message, "❌ Date format samajh nahi aaya. Dobara likhein (01-01-2000 ya 1 Jan 2000)")
            # Do not clear state, let user retry date
    elif "date" in state and "time" not in state:
        try:
            # Parse time with AM/PM
            user_time = datetime.strptime(text.upper(), "%I:%M %p").time()
            formatted_time = user_time.strftime("%H:%M") # Store as 24-hour HH:MM

            add_to_google_sheet(chat_id, state["type"], state["name"], state["date"], formatted_time)
            bot.reply_to(message, f"✅ Reminder saved!\n{state['type']} of {state['name']} on {state['date']} at {text.upper()}")
            user_state.pop(chat_id, None) # Clear state after successful reminder creation
        except Exception:
            bot.reply_to(message, "❌ Time format galat hai. Please likhein: 08:00 AM ya 07:30 PM")
            # Do not clear state, let user retry time
    else:
        # Fallback for unexpected input during conversation
        bot.reply_to(message, "Kuch galat likh diya hai. /start se dobara try karein.")
        user_state.pop(chat_id, None) # Clear state to restart conversation

# --- Flask Webhook Endpoint (Optional, primarily for Render's health check) ---
# For Render Web Service, we need something listening on a port.
# If you don't use webhooks, this is just a dummy health check.

@app.route('/')
def index():
    return "Telegram Reminder Bot is running. Visit /health for more info."

@app.route('/health')
def health_check():
    # Simple health check, can be expanded to check GSheets/Telegram API connectivity
    return "OK", 200

# --- Main Application Entry Point ---

if __name__ == '__main__':
    # Get port from Render environment, default to 5000 for local testing
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting application. Flask app will listen on port {port}.")

    # Start the schedule_checker in a separate daemon thread
    # This must be done BEFORE app.run() which is blocking
    threading.Thread(target=schedule_checker, daemon=True).start()

    # Start the bot.infinity_polling() in a separate daemon thread
    # This allows Flask to run in the main thread
    print("Starting Telegram bot polling in background thread...")
    threading.Thread(target=bot.infinity_polling, daemon=True).start()

    # Run the Flask app
    # host="0.0.0.0" makes it accessible from outside the container
    # This will block the main thread and keep the application alive,
    # ensuring Render detects an open port.
    app.run(host="0.0.0.0", port=port)
