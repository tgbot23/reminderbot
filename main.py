import os
import json
import threading
import time
from datetime import datetime
from dateutil import parser
import pytz
import schedule
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request

# --- Setup ---

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise Exception("BOT_TOKEN env variable not set")

bot = telebot.TeleBot(TOKEN)

IST = pytz.timezone("Asia/Kolkata")

app = Flask(__name__)
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask app on port {port}...")

    # Start the schedule thread
    threading.Thread(target=schedule_checker, daemon=True).start()

    # Start the bot polling in a separate thread (so Flask can run)
    threading.Thread(target=bot.infinity_polling, daemon=True).start()

    # Run Flask app (bind to all interfaces)
    app.run(host="0.0.0.0", port=port)


# --- Google Sheets Setup ---

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
        print(f"✅ Added reminder: {name} {date} {time_}")
    except Exception as e:
        print(f"❌ Error adding reminder: {e}")

# --- Reminder Sending ---

def send_reminders():
    try:
        now = datetime.now(IST)
        today = now.strftime("%d-%m")
        current_time = now.strftime("%H:%M")

        sheet = get_google_sheet()
        records = sheet.get_all_records()

        for entry in records:
            # Check if date matches today and time matches current time
            if entry.get("date", "")[:5] == today and entry.get("time", "") == current_time:
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
        print(f"❌ Error in send_reminders(): {e}")

def schedule_checker():
    schedule.every().minute.do(send_reminders)
    while True:
        schedule.run_pending()
        time.sleep(10)

# --- Start schedule thread ---

threading.Thread(target=schedule_checker, daemon=True).start()

# --- User state for conversation ---

user_state = {}

# --- Telegram Handlers ---

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Namaste! Kis cheez ka reminder chahiye?\n1. Birthday\n2. Anniversary")

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

# --- Flask webhook endpoint (optional) ---

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200

@app.route('/')
def index():
    return "Bot is running."

# --- Run Flask and bot polling ---

if __name__ == '__main__':
    # If you want to use webhook, set webhook here and run Flask only.
    # For Render free tier, long polling is easier:
    print("Bot polling started...")
    bot.infinity_polling()
    # Flask app can be run separately if webhook is used.
