import telebot
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil import parser
import pytz
import threading
import schedule
import time

# Bot token and timezone
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
IST = pytz.timezone("Asia/Kolkata")

# Load Google Sheet credentials from environment
def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Telegram Reminders").sheet1
    return sheet

# Add new reminder to sheet
def add_to_google_sheet(chat_id, type_, name, date, time_):
    try:
        sheet = get_google_sheet()
        sheet.append_row([str(chat_id), type_, name, date, time_])
        print("✅ Added to Google Sheet:", name, date, time_)
    except Exception as e:
        print("❌ Error adding to Google Sheet:", e)

# Send reminders by checking the sheet
def send_reminders():
    try:
        now = datetime.now(IST)
        current_time = now.strftime("%H:%M")
        today = now.strftime("%d-%m")

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

# Schedule checker
def schedule_checker():
    schedule.every().minute.do(send_reminders)
    while True:
        schedule.run_pending()
        time.sleep(30)

# Start schedule in background
threading.Thread(target=schedule_checker, daemon=True).start()

# Conversation flow
user_state = {}

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
        bot.reply_to(message, "Date bataiye Burthday/Anniversary ki (jaise: 01-01-2000 ya 1 Jan 2000):")
    elif "name" in state and "date" not in state:
        try:
            dob = parser.parse(text, dayfirst=True).date()
            user_state[chat_id]["date"] = dob.strftime("%d-%m-%Y")
            bot.reply_to(message, "Kitne baje reminder chahiye? (jaise: 08:00 AM ya 07:30 PM)")
        except:
            bot.reply_to(message, "❌ Date format samajh nahi aaya. Dobara likhein (01-01-2000 ya 1 Jan 2000)")
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
            user_state.pop(chat_id, None)
        except:
            bot.reply_to(message, "❌ Time format galat hai. Please likhein: 08:00 AM ya 07:30 PM")
    else:
        bot.reply_to(message, "Kuch galat likh diya hai. /start se dobara try karein.")

# Start polling
bot.remove_webhook()
bot.infinity_polling()
