from keep_alive import keep_alive
import telebot
import os
import json
import time
import schedule
import threading
import requests
from datetime import datetime
import pytz  # <-- Add this
from tzlocal import get_localzone_name

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

DATA_FILE = "reminders.json"

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

user_state = {}

def send_reminders():
    india = pytz.timezone("Asia/Kolkata")
    today = datetime.now(india).strftime("%d-%m")
    data = load_data()
    for entry in data:
        entry_date = entry["date"][:5]
        if entry_date == today:
            years = datetime.now(india).year - int(entry["date"][-4:])
            if entry["type"] == "Birthday":
                msg = f"🎂 Aaj {entry['name']} ka Birthday hai! {years} saal ke ho gaye hain. Mubarak ho!"
            else:
                msg = f"💍 Aaj {entry['name']} ki shaadi ki {years}vi anniversary hai! Mubarak ho!"
            try:
                for i in range(3):
                    try:
                        bot.send_message(entry["chat_id"], msg)
                        break
                    except requests.exceptions.ConnectionError:
                        time.sleep(2)
                    except Exception as e:
                        print(f"Error sending reminder: {e}")
                        break
            except Exception as e:
                print(f"Error sending reminder: {e}")

def schedule_checker():
    while True:
        schedule.run_pending()
        time.sleep(30)

# 🕛 Schedule reminder at 12:00 AM IST → Convert to UTC = 18:30 previous day
schedule.every().day.at("18:30").do(send_reminders)
threading.Thread(target=schedule_checker, daemon=True).start()

# Start bot when any text comes (not just /start)
@bot.message_handler(func=lambda message: message.text and message.chat.id not in user_state)
def universal_start(message):
    user_state[message.chat.id] = {}
    bot.reply_to(message, "Namaste! Kis cheez ka reminder chahiye?\n1. Birthday\n2. Anniversary\nReply 1 ya 2 bhejein.")

@bot.message_handler(func=lambda m: m.text in ["1", "2"])
def ask_name(message):
    user_state[message.chat.id] = {"type": "Birthday" if message.text == "1" else "Anniversary"}
    bot.reply_to(message, "Naam bataiye (jiska reminder chahiye):")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("type") and "name" not in user_state[m.chat.id])
def ask_date(message):
    user_state[message.chat.id]["name"] = message.text.strip()
    bot.reply_to(message, "Date bataiye (DD-MM-YYYY):")

@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("name") and "date" not in user_state[m.chat.id])
def save_reminder(message):
    try:
        dob = datetime.strptime(message.text.strip(), "%d-%m-%Y").date()
        entry = {
            "chat_id": message.chat.id,
            "type": user_state[message.chat.id]["type"],
            "name": user_state[message.chat.id]["name"],
            "date": dob.strftime("%d-%m-%Y")
        }
        data = load_data()
        data.append(entry)
        save_data(data)
        bot.reply_to(message, f"Reminder saved! {entry['type']} of {entry['name']} on {entry['date']}")
    except:
        bot.reply_to(message, "❌ Date galat hai! DD-MM-YYYY format me dobara bhejein.")
        return
    user_state.pop(message.chat.id, None)

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
