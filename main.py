import os
import json
from datetime import datetime
from dateutil import parser
import pytz
from flask import Flask, request
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# APScheduler imports
from flask_apscheduler import APScheduler

# Bot token and timezone
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
IST = pytz.timezone("Asia/Kolkata")

# Flask app
app = Flask(__name__)

# === APScheduler CONFIGURATION START ===

class Config:
    SCHEDULER_API_ENABLED = False  # no REST API needed

app.config.from_object(Config())

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

@scheduler.task('cron', id='reminder_job', minute='*')
def scheduled_remind():
    send_reminders()

# === APScheduler CONFIGURATION END ===

# Google Sheets setup
def get_google_sheet():
    scope = [...]
    creds_json = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    return client.open("Telegram Reminders").sheet1

def add_to_google_sheet(chat_id, type_, name, date, time_):
    ...

def send_reminders():
    try:
        now = datetime.now(IST)
        current_time = now.strftime("%H:%M")
        today = now.strftime("%d-%m")

        print(f"⏱️ send_reminders called — today: {today}, current_time: {current_time}")
        sheet = get_google_sheet()
        records = sheet.get_all_records()
        print(f"🔍 Retrieved {len(records)} records from Google Sheet")

        for entry in records:
            if entry["date"][:5] == today and entry["time"] == current_time:
                years = now.year - int(entry["date"][-4:])
                msg = (f"🎂 Aaj {entry['name']} ka Birthday hai! {years} saal ke ho gaye hain. Mubarak ho!"
                       if entry["type"] == "Birthday"
                       else f"💍 Aaj {entry['name']} ki shaadi ki {years}vi anniversary hai! Mubarak ho!")
                try:
                    bot.send_message(int(entry["chat_id"]), msg)
                    print(f"✅ Reminder sent to {entry['name']} at {entry['chat_id']}")
                except Exception as e:
                    print(f"❌ Error sending reminder: {e}")
    except Exception as e:
        print("❌ Error in send_reminders():", e)

# Telegram handlers and webhook setup (unchanged)
...

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=f"{os.environ.get('RENDER_APP_URL')}/{TOKEN}")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
