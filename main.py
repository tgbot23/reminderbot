import os
import json
import telebot
import gspread
import pytz
import threading
from flask import Flask, request
from datetime import datetime
from dateutil import parser
from oauth2client.service_account import ServiceAccountCredentials
import schedule
import time

# Telegram & Timezone setup
TOKEN = os.environ["BOT_TOKEN"]
bot = telebot.TeleBot(TOKEN)
IST = pytz.timezone("Asia/Kolkata")

# Flask app for webhook
app = Flask(__name__)

# State tracking for user interaction
user_state = {}

# Load Google Sheet
def get_sheet():
    creds_json = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    return client.open("Telegram reminders").sheet1

# Add reminder to sheet
def add_reminder(chat_id, type_, name, date, time_):
    try:
        sheet = get_sheet()
        sheet.append_row([str(chat_id), type_, name, date, time_])
        print(f"✅ Added to sheet: {name} - {date} {time_}")
    except Exception as e:
        print("❌ Error saving to sheet:", e)

# Send scheduled reminders
def send_reminders():
    try:
        now = datetime.now(IST)
        current_date = now.strftime("%d-%m")
        current_time = now.strftime("%H:%M")
        sheet = get_sheet()
        rows = sheet.get_all_records()
        for row in rows:
            if row["date"][:5] == current_date and row["time"] == current_time:
                years = now.year - int(row["date"][-4:])
                if row["type"] == "Birthday":
                    msg = f"🎂 Aaj {row['name']} ka birthday hai! {years} saal ke ho gaye hain. Mubarak ho!"
                else:
                    msg = f"💍 Aaj {row['name']} ki {years}vi shaadi ki saalgirah hai! Mubarak ho!"
                try:
                    bot.send_message(int(row["chat_id"]), msg)
                    print(f"✅ Reminder sent to {row['name']}")
                except Exception as e:
                    print("❌ Sending failed:", e)
    except Exception as e:
        print("❌ Error in send_reminders():", e)

# Scheduler thread
def schedule_worker():
    schedule.every().minute.do(send_reminders)
    print("✅ Scheduler thread started")
    while True:
        schedule.run_pending()
        time.sleep(30)

threading.Thread(target=schedule_worker, daemon=True).start()

# Flask webhook endpoint
@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "POST":
        bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
        return "OK", 200
    return "Running", 200

# Telegram Bot interaction
@bot.message_handler(commands=["start"])
def send_welcome(message):
    chat_id = message.chat.id
    user_state[chat_id] = {}
    bot.send_message(chat_id, "Namaste! Reminder kis cheez ka chahiye?\n1. Birthday\n2. Anniversary")

@bot.message_handler(func=lambda m: True)
def handle_input(message):
    chat_id = message.chat.id
    text = message.text.strip()
    state = user_state.get(chat_id, {})

    if not state:
        if text in ["1", "2"]:
            user_state[chat_id] = {"type": "Birthday" if text == "1" else "Anniversary"}
            bot.send_message(chat_id, "Naam bataiye jiska reminder chahiye:")
        else:
            bot.send_message(chat_id, "Pehle choose karein:\n1. Birthday\n2. Anniversary")
    elif "type" in state and "name" not in state:
        user_state[chat_id]["name"] = text
        bot.send_message(chat_id, "Date bataiye (e.g. 15-07-2000 ya 15 July 2000):")
    elif "name" in state and "date" not in state:
        try:
            dt = parser.parse(text, dayfirst=True).date()
            user_state[chat_id]["date"] = dt.strftime("%d-%m-%Y")
            bot.send_message(chat_id, "Reminder kis time chahiye? (jaise: 01:30 PM):")
        except:
            bot.send_message(chat_id, "❌ Date samajh nahi aayi. Format: 15-07-2000 ya 15 July 2000")
    elif "date" in state and "time" not in state:
        try:
            user_time = datetime.strptime(text.upper(), "%I:%M %p").time()
            final_time = user_time.strftime("%H:%M")

            data = {
                "chat_id": chat_id,
                "type": state["type"],
                "name": state["name"],
                "date": state["date"],
                "time": final_time
            }

            add_reminder(**data)
            bot.send_message(chat_id, f"✅ Reminder saved for {data['name']} on {data['date']} at {text.upper()}")
            user_state.pop(chat_id)
        except:
            bot.send_message(chat_id, "❌ Time galat hai. Format: 01:30 PM")
    else:
        bot.send_message(chat_id, "Kuch galat hua. /start se dobara shuru karein.")

# Webhook setup (only needed once or when restarting)
WEBHOOK_URL = os.environ.get("RENDER_APP_URL")
if WEBHOOK_URL:
    bot.remove_webhook()
    bot.set_webhook(f"{WEBHOOK_URL}/")

