from keep_alive import keep_alive
import telebot
import os
import json
import threading
import time
import schedule
import requests
from datetime import datetime
from dateutil import parser
import pytz

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
IST = pytz.timezone("Asia/Kolkata")

DATA_FILE = "reminders.json"
user_state = {}

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def send_reminders():
    now = datetime.now(IST)
    current_time = now.strftime("%H:%M")
    today = now.strftime("%d-%m")

    data = load_data()
    for entry in data:
        entry_date = entry["date"][:5]
        if entry_date == today and entry["time"] == current_time:
            years = now.year - int(entry["date"][-4:])
            if entry["type"] == "Birthday":
                msg = f"🎂 Aaj {entry['name']} ka Birthday hai! {years} saal ke ho gaye hain. Mubarak ho!"
            else:
                msg = f"💍 Aaj {entry['name']} ki shaadi ki {years}vi anniversary hai! Mubarak ho!"
            try:
                bot.send_message(entry["chat_id"], msg)
            except Exception as e:
                print(f"Error sending reminder: {e}")

def schedule_checker():
    while True:
        schedule.run_pending()
        time.sleep(30)

schedule.every().minute.do(send_reminders)
threading.Thread(target=schedule_checker, daemon=True).start()

@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "Namaste! Kis cheez ka reminder chahiye?\n1. Birthday\n2. Anniversary\nReply 1 ya 2 bhejein.")

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    text = message.text.strip()

    state = user_state.get(chat_id, {})

    if not state:
        if text in ["1", "2"]:
            user_state[chat_id] = {"type": "Birthday" if text == "1" else "Anniversary"}
            bot.reply_to(message, "Naam bataiye (jiska reminder chahiye):")
        else:
            bot.reply_to(message, "Namaste! Reminder set karne ke liye pehle choose karein:\n1. Birthday\n2. Anniversary")
    elif "type" in state and "name" not in state:
        user_state[chat_id]["name"] = text
        bot.reply_to(message, "Date bataiye (jaise: 01-01-2000 ya 1 Jan 2000):")
    elif "name" in state and "date" not in state:
        try:
            dob = parser.parse(text, dayfirst=True).date()
            user_state[chat_id]["date"] = dob.strftime("%d-%m-%Y")
            bot.reply_to(message, "Kitne baje reminder chahiye? (12-hour format jaise 08:00 AM ya 07:30 PM)")
        except:
            bot.reply_to(message, "❌ Date format samajh nahi aaya. Dobara likhein (jaise: 01-01-2000 ya 1 Jan 2000):")
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
            data = load_data()
            data.append(entry)
            save_data(data)
            bot.reply_to(message, f"✅ Reminder saved!\n{entry['type']} of {entry['name']} on {entry['date']} at {text.upper()}")
            user_state.pop(chat_id, None)
        except:
            bot.reply_to(message, "❌ Time format galat hai. Please likhein jaise: 08:00 AM ya 07:30 PM")
    else:
        bot.reply_to(message, "❌ Kuch galat likh diya hai. Phir se /start likhein.")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
