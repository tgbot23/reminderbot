import os, json, threading, time
from datetime import datetime
from dateutil import parser
import pytz, schedule, telebot, gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask
from keep_alive import keep_alive

# --- Config ---
TOKEN = os.environ["BOT_TOKEN"]
bot = telebot.TeleBot(TOKEN)
IST = pytz.timezone("Asia/Kolkata")
app = Flask(__name__)

# --- Google Sheets ---
def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds).open("Telegram Reminders").sheet1

def add_to_google_sheet(chat_id, type_, name, date, time_):
    try:
        get_google_sheet().append_row([str(chat_id), type_, name, date, time_])
        print(f"✅ Added reminder: {name}, {date} {time_}")
    except Exception as e:
        print("❌ Error adding to sheet:", e)

# --- Reminders ---
def send_reminders():
    now = datetime.now(IST)
    print("⏰ Checking reminders at", now.strftime("%Y-%m-%d %H:%M:%S"))
    try:
        sheet = get_google_sheet()
        for e in sheet.get_all_records():
            dt = parser.parse(f"{e['date']} {e['time']}", dayfirst=True).replace(tzinfo=IST)
            if abs((now - dt).total_seconds()) < 120:
                msg = (f"🎂 Birthday: {e['name']}" if e["type"] == "Birthday"
                       else f"💍 Anniversary: {e['name']}")
                bot.send_message(int(e["chat_id"]), msg)
                print("✅ Sent:", msg)
    except Exception as e:
        print("❌ Error in send_reminders():", e)

def schedule_checker():
    print("✅ Scheduler thread started")
    schedule.every().minute.do(send_reminders)
    while True:
        schedule.run_pending()
        print("🔄 Pending check running...")
        time.sleep(1)

# --- Telegram Handlers ---
user_state = {}
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "Namaste! Reminder set karein: 1. Birthday  2. Anniversary")
    user_state[msg.chat.id] = {}

@bot.message_handler(func=lambda m: True)
def handle_msg(msg):
    cid = msg.chat.id; txt = msg.text.strip(); st = user_state.get(cid, {})
    # (Rest of your existing state logic)
    # On final time entry: call add_to_google_sheet()

# --- Launching ---
if __name__ == "__main__":
    threading.Thread(target=schedule_checker).start()
    threading.Thread(target=bot.infinity_polling).start()
    keep_alive()
    port = int(os.environ.get("PORT", 5000))
    print("🌐 Flask running on port", port)
    app.run(host="0.0.0.0", port=port)
