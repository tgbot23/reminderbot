import os
import json
import threading
import time
from datetime import datetime
from dateutil import parser
import pytz
import schedule

from flask import Flask, request
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Bot token and timezone
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
IST = pytz.timezone("Asia/Kolkata")

# Flask app
app = Flask(__name__)

# Google Sheets setup
def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Telegram Reminders").sheet1
    return sheet

def add_to_google_sheet(chat_id, type_, name, date, time_):
    try:
        sheet = get_google_sheet()
        sheet.append_row([str(chat_id), type_, name, date, time_])
        print("✅ Added to Google Sheet:", name, date, time_)
    except Exception as e:
        print("❌ Error adding to Google Sheet:", e)

def send_reminders():
    try:
        now = datetime.now(IST)
        current_time = now.strftime("%H:%M")
        today = now.strftime("%d-%m")
         print(f"⏱️ send_reminders called — today: {today}, current_time: {current_time}")
        sheet = get_google_sheet()
        records = sheet.get_all_records()
        print(f"🔍 Retrieved {len(records)} records from Google Sheet")

        sheet = get_google_sheet()
        records = sheet.get_all_records()

        for entry in records:
            if entry["date"][:5] == today and entry["time"] == current_time:
                years = now.year - int(entry["date"][-4:])
                if entry["type"] == "Birthday":
                    msg = f"🎂 Aaj {entry['name']} ka Birthday hai! {years} saal ke ho gaye hain. Mubarak ho!"
                else:
                    msg = f"💍 Aaj {entry['name']} ki shaadi ki {years}vi anniversary hai! Mubarak ho!"
                try:
                    bot.send_message(int(entry["chat_id"]), msg)
                    print(f"✅ Reminder sent to {entry['name']} at {entry['chat_id']}")
                except Exception as e:
                    print(f"❌ Error sending reminder: {e}")
    except Exception as e:
        print("❌ Error in send_reminders():", e)

def schedule_checker():
    schedule.every().minute.do(send_reminders)
    while True:
        schedule.run_pending()
        except Exception as e:
            print("❌ Scheduler crashed:", e)
        time.sleep(1)  # reduced from 30 seconds for quicker retries

# Start schedule in background thread
threading.Thread(target=schedule_checker, daemon=True).start()

# Telegram bot handlers
user_state = {}

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_state[chat_id] = {} # Clear state on /start
    bot.reply_to(message, "Namaste! Kis cheez ka reminder chahiye?\n1. Birthday\n2. Anniversary")

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    chat_id = message.chat.id
    text = message.text.strip()
    state = user_state.get(chat_id, {})

    # Stage 0: Choose reminder type (Birthday/Anniversary)
    if not state:
        if text == "1":
            user_state[chat_id] = {"type": "Birthday"}
            bot.reply_to(message, "Achha, Birthday! Kiska Birthday hai? Naam bataiye:")
        elif text == "2":
            user_state[chat_id] = {"type": "Anniversary"}
            bot.reply_to(message, "Achha, Anniversary! Kiska ya kiski Anniversary hai? Naam bataiye:")
        else:
            bot.reply_to(message, "Mujhe samajh nahi aaya. Please choose karein:\n1. Birthday\n2. Anniversary")
            # Don't change state, keep them at this stage
    
    # Stage 1: Get name
    elif "type" in state and "name" not in state:
        if len(text) > 2 and len(text) < 50 and all(char.isalpha() or char.isspace() for char in text): # Basic name validation
            user_state[chat_id]["name"] = text
            bot.reply_to(message, f"Theek hai, {text}. Ab {state['type']} ki date bataiye (jaise: 01-01-2000 ya 1 Jan 2000):")
        else:
            bot.reply_to(message, "Mafi chahunga, naam theek se nahi likha. Kripya naam dobara likhein (sirf akshar):")
            # Don't change state
    
    # Stage 2: Get date
    elif "name" in state and "date" not in state:
        try:
            # Try parsing with dayfirst=True first
            dob = parser.parse(text, dayfirst=True).date()
            user_state[chat_id]["date"] = dob.strftime("%d-%m-%Y")
            bot.reply_to(message, "Kitne baje reminder chahiye? (jaise: 08:00 AM ya 07:30 PM)")
        except ValueError: # Changed from generic 'except' to specific 'ValueError'
            bot.reply_to(message, "❌ Date format samajh nahi aaya. Kripya date dobara likhein (01-01-2000 ya 1 Jan 2000):")
            # Don't change state
    
    # Stage 3: Get time and save reminder
    elif "date" in state and "time" not in state:
        try:
            user_time = datetime.strptime(text.upper(), "%I:%M %p").time()
            formatted_time = user_time.strftime("%H:%M")

            entry = {
                "chat_id": chat_id,
                "type": state["type"],
                "name": state["name"],
                "date": state["date"],
                "time": formatted_time
            }

            add_to_google_sheet(chat_id, entry["type"], entry["name"], entry["date"], entry["time"])
            bot.reply_to(message, f"✅ Reminder saved!\n{entry['type']} of {entry['name']} on {entry['date']} at {text.upper()}")
            user_state.pop(chat_id, None) # Clear state after successful reminder saving
        except ValueError: # Changed from generic 'except' to specific 'ValueError'
            bot.reply_to(message, "❌ Time format galat hai. Kripya time dobara likhein: 08:00 AM ya 07:30 PM")
            # Don't change state
    
    # If somehow in an invalid state (should not happen with proper flow)
    else:
        bot.reply_to(message, "Kuch gadbad ho gayi hai. Kripya /start se dobara shuru karein.")
        user_state.pop(chat_id, None) # Clear state to allow restart

# Flask route for Telegram webhook
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200

@app.route('/')
def index():
    return "Bot is running"

if __name__ == '__main__':
    # Remove any previous webhook
    bot.remove_webhook()

    # Set webhook URL - replace with your actual Render app URL
    RENDER_APP_URL = os.environ.get("RENDER_APP_URL")  # e.g. "https://your-app.onrender.com"
    if not RENDER_APP_URL:
        # Fallback for local testing or if RENDER_APP_URL is not set
        print("Warning: RENDER_APP_URL environment variable not set. Assuming local test.")
        webhook_url = f"https://your-local-ngrok-url/{TOKEN}" # Replace with ngrok or similar for local webhook testing
    else:
        webhook_url = f"{RENDER_APP_URL}/{TOKEN}"

    bot.set_webhook(url=webhook_url)
    print(f"Webhook set to {webhook_url}")

    # Run Flask app on the port Render provides
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask app on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port)

