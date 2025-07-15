import os, json, threading, time
from datetime import datetime
from dateutil import parser
import pytz, schedule, telebot, gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request

# --- Config ---
TOKEN = os.environ["BOT_TOKEN"]
HOST = os.environ["RENDER_EXTERNAL_HOSTNAME"]
WEBHOOK_URL = f"https://{HOST}/{TOKEN}"
bot = telebot.TeleBot(TOKEN, threaded=False)
IST = pytz.timezone("Asia/Kolkata")
user_state = {}

# --- Google Sheets ---
def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(os.environ["GOOGLE_CREDS_JSON"]), scope)
    return gspread.authorize(creds).open("Telegram Reminders").sheet1

def add_to_google_sheet(chat_id, type_, name, date, time_):
    get_google_sheet().append_row([str(chat_id), type_, name, date, time_])
    print(f"✅ Added reminder: {name}, {date} {time_}")

# --- Scheduler ---
def send_reminders():
    now = datetime.now(IST)
    for e in get_google_sheet().get_all_records():
        dt = parser.parse(f"{e['date']} {e['time']}", dayfirst=True).replace(tzinfo=IST)
        diff = (now - dt).total_seconds()
        if 0 <= diff < 60:
            years = now.year - dt.year
            msg = (f"🎂 Aaj {e['name']} ka Birthday hai! {years} saal ho gaye 🎉"
                   if e['type']=="Birthday"
                   else f"💍 Aaj {e['name']} ki shaadi ka {years}vi anniversary hai! 🎉")
            bot.send_message(int(e["chat_id"]), msg)
            print("✅ Sent:", msg)

def schedule_checker():
    schedule.every(30).seconds.do(send_reminders)
    while True:
        schedule.run_pending()
        time.sleep(1)

# --- Bot Handlers ---
@bot.message_handler(commands=['start'])
def handle_start(msg):
    cid = msg.chat.id
    bot.send_message(cid, "Namaste! Reminder ke liye:\n1️⃣ Birthday\n2️⃣ Anniversary")
    user_state[cid] = {}

@bot.message_handler(func=lambda m: True)
def handle_message(msg):
    cid, txt = msg.chat.id, msg.text.strip()
    state = user_state.get(cid, {})

    if not state:
        if txt in ["1","2"]:
            state["type"] = "Birthday" if txt=="1" else "Anniversary"
            user_state[cid] = state
            bot.send_message(cid, "Naam bataiye:")
        else:
            bot.send_message(cid, "1 ya 2 choose karein:")
    elif "name" not in state:
        state["name"] = txt
        bot.send_message(cid, "Date (DD-MM-YYYY):")
    elif "date" not in state:
        try:
            dt = parser.parse(txt, dayfirst=True).date()
            state["date"] = dt.strftime("%d-%m-%Y")
            bot.send_message(cid, "Time (08:00 AM):")
        except:
            bot.send_message(cid, "Date format sahi nahi. Try DD-MM-YYYY.")
    elif "time" not in state:
        try:
            tm = datetime.strptime(txt.upper(), "%I:%M %p").time()
            state["time"] = tm.strftime("%H:%M")
            add_to_google_sheet(cid, state["type"], state["name"], state["date"], state["time"])
            bot.send_message(cid, f"✅ Reminder saved!")
            user_state.pop(cid, None)
        except:
            bot.send_message(cid, "Time galat hai. Format: 08:00 AM.")
    else:
        bot.send_message(cid, "❌ Error. /start se dobara karein.")
        user_state.pop(cid, None)

# --- Webhook & Flask setup ---
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    threading.Thread(target=schedule_checker, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
