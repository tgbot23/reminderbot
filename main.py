import os
import json
import threading
import time
from datetime import datetime, timedelta
from dateutil import parser
import pytz
import schedule
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask

# --- Configuration & Setup ---
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set. Please set it on Render.")

bot = telebot.TeleBot(TOKEN)
IST = pytz.timezone("Asia/Kolkata")
app = Flask(__name__)

# --- Google Sheets Functions ---
def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json_str = os.environ.get("GOOGLE_CREDS_JSON")
    if not creds_json_str:
        raise ValueError("GOOGLE_CREDS_JSON environment variable not set. Please set it on Render.")
    creds_json = json.loads(creds_json_str)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Telegram Reminders").sheet1
    return sheet

def add_to_google_sheet(chat_id, type_, name, date, time_):
    try:
        sheet = get_google_sheet()
        sheet.append_row([str(chat_id), type_, name, date, time_])
        print(f"✅ Added reminder to Google Sheet: {name}, {date}, {time_}")
    except Exception as e:
        print(f"❌ Error adding to Google Sheet: {e}")

# --- Reminder Sending Logic ---
def send_reminders():
    print(f"Checking for reminders at {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        now = datetime.now(IST)
        today = now.strftime("%d-%m")

        sheet = get_google_sheet()
        records = sheet.get_all_records()

        for entry in records:
            entry_date = entry.get("date", "")
            entry_time_str = entry.get("time", "")

            if entry_date.startswith(today):
                try:
                    reminder_time_obj = datetime.strptime(entry_time_str, "%H:%M").time()
                    reminder_datetime = datetime.combine(now.date(), reminder_time_obj).replace(tzinfo=IST)
                    time_difference = abs((now - reminder_datetime).total_seconds())

                    if time_difference < 120:
                        years = now.year - int(entry_date[-4:])
                        if entry["type"] == "Birthday":
                            msg = f"🎂 Aaj {entry['name']} ka Birthday hai! {years} saal ke ho gaye hain. Mubarak ho!"
                        else:
                            msg = f"💍 Aaj {entry['name']} ki shaadi ki {years}vi anniversary hai! Mubarak ho!"
                        try:
                            bot.send_message(int(entry["chat_id"]), msg)
                            print(f"✅ Reminder sent to {entry['name']} (chat_id: {entry['chat_id']})")
                        except Exception as e:
                            print(f"❌ Error sending reminder to {entry['chat_id']}: {e}")
                except Exception as e:
                    print(f"❌ Error processing reminder entry {entry}: {e}")
    except Exception as e:
        print(f"❌ Error in send_reminders(): {e}")

def schedule_checker():
    print("Starting schedule checker thread...")
    schedule.every().minute.do(send_reminders)
    while True:
        schedule.run_pending()
        time.sleep(1)

# --- User State Management ---
user_state = {}

# --- Telegram Handlers ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Namaste! Kis cheez ka reminder chahiye?\n1. Birthday\n2. Anniversary")
    user_state[message.chat.id] = {}

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    chat_id = message.chat.id
    text = message.text.strip()
    state = user_state.get(chat_id, {})

    if not state:
        if text in ["1", "2"]:
            user_state[chat_id] = {"type": "Birthday" if text == "1" else "Anniversary"}
            bot.reply_to(message, "Naam bataiye (jiska reminder chahiye):")
        else:
            bot.reply_to(message, "Pehle choose karein:\n1. Birthday\n2. Anniversary")
            user_state.pop(chat_id, None)
    elif "type" in state and "name" not in state:
        user_state[chat_id]["name"] = text
        bot.reply_to(message, "Date bataiye Birthday/Shaadi ki (jaise: 01-01-2000 ya 1 Jan 2000):")
    elif "name" in state and "date" not in state:
        try:
            dob = parser.parse(text, dayfirst=True).date()
            user_state[chat_id]["date"] = dob.strftime("%d-%m-%Y")
            bot.reply_to(message, "Kitne baje reminder chahiye? (jaise: 08:00 AM ya 07:30 PM)")
        except Exception:
            bot.reply_to(message, "❌ Date format samajh nahi aaya. Dobara likhein (01-01-2000 ya 1 Jan 2000)")
    elif "date" in state and "time" not in state:
        try:
            user_time = datetime.strptime(text.upper(), "%I:%M %p").time()
            formatted_time = user_time.strftime("%H:%M")
            add_to_google_sheet(chat_id, state["type"], state["name"], state["date"], formatted_time)
            bot.reply_to(message, f"✅ Reminder saved!\n{state['type']} of {state['name']} on {state['date']} at {text.upper()}")
            user_state.pop(chat_id, None)
        except Exception:
            bot.reply_to(message, "❌ Time format galat hai. Please likhein: 08:00 AM ya 07:30 PM")
    else:
        bot.reply_to(message, "Kuch galat likh diya hai. /start se dobara try karein.")
        user_state.pop(chat_id, None)

# --- Flask Webhook Endpoint (Health Check) ---
@app.route('/')
def index():
    return "Telegram Reminder Bot is running."

@app.route('/health')
def health_check():
    return "OK", 200

# --- Main Entrypoint ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask on port {port}")

    # Start scheduler in a daemon thread
    threading.Thread(target=schedule_checker, daemon=True).start()

    # Start Flask app in a separate thread so that bot polling can run in main thread
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()

    print("Starting Telegram bot polling (main thread)...")
    # Run bot.infinity_polling() in main thread to avoid Telegram 409 error
    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            print(f"Polling error: {e}. Restarting polling in 5 seconds...")
            time.sleep(5)
