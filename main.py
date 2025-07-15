import os
import json
import gspread
import telebot
from flask import Flask, request
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from dateutil import parser
import pytz

# Init
TOKEN = os.environ["BOT_TOKEN"]
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
IST = pytz.timezone("Asia/Kolkata")
user_state = {}

# Google Sheets
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(os.environ["GOOGLE_CREDS_JSON"]), scope)
    sheet = gspread.authorize(creds).open("Telegram Reminders").sheet1
    return sheet

def add_reminder(chat_id, type_, name, date, time_):
    sheet = get_sheet()
    sheet.append_row([str(chat_id), name, type_, date, time_])
    print(f"✅ Added: {name}, {type_}, {date} at {time_}")

# Scheduler Task
def send_reminders():
    now = datetime.now(IST)
    today = now.strftime("%d-%m")
    now_time = now.strftime("%H:%M")

    sheet = get_sheet()
    data = sheet.get_all_records()
    
    for row in data:
        if row['date'][:5] == today and row['time'] == now_time:
            year = now.year - int(row['date'][-4:])
            if row['type'].lower() == "birthday":
                msg = f"🎂 Aaj {row['name']} ka Birthday hai! {year} saal ke ho gaye hain. Mubarak ho!"
            else:
                msg = f"💍 Aaj {row['name']} ki {year}vi Anniversary hai! Mubarak ho!"
            try:
                bot.send_message(int(row["chat_id"]), msg)
                print(f"✅ Sent reminder to {row['name']}")
            except Exception as e:
                print(f"❌ Error sending message: {e}")

# Setup scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(send_reminders, "interval", minutes=1)
scheduler.start()

# Bot conversation
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    user_state[chat_id] = {}
    bot.send_message(chat_id, "Namaste! Reminder chahiye:\n1. Birthday\n2. Anniversary")

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    chat_id = message.chat.id
    text = message.text.strip()
    state = user_state.get(chat_id, {})

    if not state:
        if text in ["1", "2"]:
            user_state[chat_id] = {"type": "Birthday" if text == "1" else "Anniversary"}
            bot.send_message(chat_id, "Naam bataiye jiska reminder chahiye:")
        else:
            bot.send_message(chat_id, "❌ Please choose 1 or 2:\n1. Birthday\n2. Anniversary")
    elif "type" in state and "name" not in state:
        state["name"] = text
        bot.send_message(chat_id, "Date likhiye (01-01-2000 ya 1 Jan 2000):")
    elif "name" in state and "date" not in state:
        try:
            dob = parser.parse(text, dayfirst=True).date()
            state["date"] = dob.strftime("%d-%m-%Y")
            bot.send_message(chat_id, "Time likhiye (08:00 AM ya 07:30 PM):")
        except:
            bot.send_message(chat_id, "❌ Date format galat hai.")
    elif "date" in state and "time" not in state:
        try:
            user_time = datetime.strptime(text.upper(), "%I:%M %p").time()
            formatted_time = user_time.strftime("%H:%M")
            state["time"] = formatted_time
            add_reminder(chat_id, state["type"], state["name"], state["date"], state["time"])
            bot.send_message(chat_id, f"✅ Reminder saved for {state['name']} at {text.upper()}")
            user_state.pop(chat_id, None)
        except:
            bot.send_message(chat_id, "❌ Time format galat hai.")
    else:
        bot.send_message(chat_id, "❌ Error. Dobara /start karein.")

# Flask webhook route
@app.route("/")
def home():
    return "Bot is running"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK"

# Set webhook
bot.remove_webhook()
bot.set_webhook(url=f"{os.environ['RENDER_APP_URL']}/{TOKEN}")

# Flask run
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
