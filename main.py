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
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

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
    sheet.append_row([str(chat_id), type_, name, date, time_])
    print(f"✅ Added: {name}, {type_}, {date} at {time_}")

# Scheduler Task
def send_reminders():
    now = datetime.now(IST)
    sheet = get_sheet()
    data = sheet.get_all_records()

    for row in data:
        try:
            reminder_date = datetime.strptime(row['date'].strip(), "%d-%m-%Y")
            reminder_time = datetime.strptime(row['time'].strip(), "%H:%M").time()

            if reminder_date.day == now.day and reminder_date.month == now.month:
                reminder_datetime = datetime.combine(now.date(), reminder_time)
                if reminder_datetime.tzinfo is None:
                    reminder_datetime = IST.localize(reminder_datetime)
                time_diff = abs((reminder_datetime - now).total_seconds())
                print(f"Now IST: {now.strftime('%d-%m-%Y %H:%M:%S')}, Reminder Time: {reminder_datetime.strftime('%d-%m-%Y %H:%M:%S')}, Diff: {time_diff}")
                if time_diff <= 60:
                    name = row['name']
                    if row['type'].lower() == "birthday":
                        msg = (
                            f"🎉 *Hello Hello! Jaldi se {name} ko wish kar do!* 🎂\n"
                            f"Aaj inka *Birthday* hai 😍\n"
                            f"Zindagi ka ek aur beautiful saal jud gaya 💫\n"
                            f"Unhe ek pyaara sa message bhejna na bhoolna 💌\n\n"
                            f"🎈 *Janamdin ki hardik shubhkamnaye , {name}!* 🎊"
                        )
                        wish_text = f"Happy Birthday, {name}! 🎂"
                    else:
                        msg = (
                            f"💖 *Aree suno suno! Aaj hai {name} ki Shaadi ki Salgirah!* 💍\n"
                            f"🎊 Pyar bhara din hai... ek aur saal milke jeene ka 🥰\n"
                            f"Unko aur unke jeevan saathi ko bhejo *Dil se Salgirah ki Shubhkamnaye* ❤️\n\n"
                            f"🌹 *Happy Anniversary, {name}!* 💐"
                        )
                        wish_text = f"Happy Anniversary, {name}! 💍"

                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(InlineKeyboardButton("🎉 Wish Now", switch_inline_query=wish_text))
                    bot.send_message(int(row["chat_id"]), msg, parse_mode="Markdown", reply_markup=keyboard)
                    print(f"✅ Sent reminder to {row['name']}")
                else:
                    print(f"⏱ Not time yet for {row['name']}")
            else:
                print(f"📅 Not today for {row['name']}")
        except Exception as e:
            print(f"❌ Error processing row: {e}")

# Setup scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(send_reminders, "interval", minutes=1)
scheduler.start()

# Bot conversation
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    user_state[chat
