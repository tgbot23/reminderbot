from keep_alive import keep_alive
import telebot
import os
import json
import threading
import schedule
import time
import requests
from datetime import datetime
import pytz
from dateutil import parser

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

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

# Universal message handler – starts conversation if not already in flow.
@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    text = message.text.strip()

    # Step 1: If user not in conversation, ask for reminder type
    if chat_id not in user_state or not user_state[chat_id]:
        user_state[chat_id] = {}
        bot.send_message(chat_id, "Namaste! Kis cheez ka reminder chahiye?\n1. Birthday\n2. Anniversary\nKripya 1 ya 2 bhejein.")
        return

    # Step 2: Type selection
    if "type" not in user_state[chat_id]:
        if text == "1":
            user_state[chat_id]["type"] = "Birthday"
        elif text == "2":
            user_state[chat_id]["type"] = "Anniversary"
        else:
            bot.send_message(chat_id, "❌ Galat option! Sirf 1 ya 2 bhejein.\n1 for Birthday, 2 for Anniversary.")
            return
        bot.send_message(chat_id, "Naam bataiye (jiska reminder chahiye):")
        return

    # Step 3: Name input
    if "type" in user_state[chat_id] and "name" not in user_state[chat_id]:
        user_state[chat_id]["name"] = text
        bot.send_message(chat_id, "Date bataiye (kisi bhi format mein, jaise: 1 Jan 2000, 01-01-2000 ya 01/01/2000):")
        return

    # Step 4: Date input
    if "name" in user_state[chat_id] and "date" not in user_state[chat_id]:
        try:
            dob = parser.parse(text, dayfirst=True).date()
            user_state[chat_id]["date"] = dob.strftime("%d-%m-%Y")
            bot.send_message(chat_id, "Reminder kis samay bhejna hai? (e.g., 07:00 AM ya 09:30 PM IST)")
        except Exception:
            bot.send_message(chat_id, "❌ Date samajh nahi aayi. Kripya sahi format mein date bhejein (e.g., 1 Jan 2000, 01-01-2000)")
        return

    # Step 5: Time input for reminder (in IST)
    if "date" in user_state[chat_id] and "time" not in user_state[chat_id]:
        time_input = text.upper()
        try:
            # Convert user-specified IST time (e.g., 07:00 AM) to 24-hour UTC time.
            # First, parse the time input (we use a dummy date)
            user_time = datetime.strptime(time_input, "%I:%M %p").time()

            # Create a datetime object for IST using today's dummy date.
            ist_datetime = datetime.combine(datetime.today(), user_time)
            # Adjust IST to UTC (IST = UTC + 5:30, so UTC = IST - 5:30)
            utc_datetime = (ist_datetime - pytz.timedelta(hours=5, minutes=30)).time()

            user_state[chat_id]["time"] = utc_datetime.strftime("%H:%M")
            entry = {
                "chat_id": chat_id,
                "type": user_state[chat_id]["type"],
                "name": user_state[chat_id]["name"],
                "date": user_state[chat_id]["date"],
                "time": user_state[chat_id]["time"]
            }
            data = load_data()
            data.append(entry)
            save_data(data)
            bot.send_message(chat_id, f"✅ Reminder set ho gaya!\n{entry['type']} of {entry['name']} on {entry['date']}.\nNotification aapko har saal us din user-set time (IST) par milegi.")
            user_state.pop(chat_id, None)
        except Exception as e:
            bot.send_message(chat_id, "❌ Time format galat hai. Kripya sahi format mein time bhejein (e.g., 07:00 AM ya 09:30 PM)")
        return

# Reminder sender function
def send_reminders():
    # Use IST timezone to check today's date.
    india_tz = pytz.timezone("Asia/Kolkata")
    now_india = datetime.now(india_tz)
    today = now_india.strftime("%d-%m")
    # Convert current IST time to UTC time (for matching saved entries)
    now_utc = (now_india - india_tz.utcoffset(now_india)).strftime("%H:%M")
    data = load_data()
    for entry in data:
        # Entry date stored as DD-MM-YYYY; compare first 5 characters (DD-MM)
        if entry["date"][:5] == today and entry["time"] == now_utc:
            years = now_india.year - int(entry["date"][-4:])
            if entry["type"] == "Birthday":
                msg = f"🎂 Aaj {entry['name']} ka Birthday hai! {years} saal ke ho gaye hain. Mubarak ho!"
            else:
                msg = f"💍 Aaj {entry['name']} ki shaadi ki {years}vi anniversary hai! Mubarak ho!"
            try:
                bot.send_message(entry["chat_id"], msg)
            except Exception as e:
                print(f"❌ Error sending reminder: {e}")

# Scheduler thread that runs every minute.
def schedule_checker():
    while True:
        schedule.run_pending()
        time.sleep(30)

# Schedule reminders: We check every minute.
schedule.every(1).minutes.do(send_reminders)
threading.Thread(target=schedule_checker, daemon=True).start()

# Start the bot along with keep_alive() for hosting platforms.
if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
