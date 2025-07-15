import os, json, threading, time
from datetime import datetime
from dateutil import parser
import pytz, schedule, telebot, gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Config ---
TOKEN = os.environ["BOT_TOKEN"]
bot = telebot.TeleBot(TOKEN)
IST = pytz.timezone("Asia/Kolkata")
user_state = {}

# --- Google Sheets ---
def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    return gspread.authorize(creds).open("Telegram Reminders").sheet1

def add_to_google_sheet(chat_id, type_, name, date, time_):
    get_google_sheet().append_row([str(chat_id), type_, name, date, time_])
    print(f"✅ Added reminder: {name}, {date} {time_}")

# --- Reminder Checker ---
def send_reminders():
    now = datetime.now(IST)
    sheet = get_google_sheet()
    for e in sheet.get_all_records():
        dt = parser.parse(f"{e['date']} {e['time']}", dayfirst=True).replace(tzinfo=IST)
        diff = (now - dt).total_seconds()
        if 0 <= diff < 60:  # within 1 minute window
            years = now.year - dt.year
            msg = (f"🎂 Aaj {e['name']} ka Birthday hai! {years} saal ho gaye 🎉"
                   if e['type']=="Birthday"
                   else f"💍 Aaj {e['name']} ki shaadi ki {years}vi anniversary hai! Mubarak ho! 🎉")
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
    bot.send_message(cid, "Namaste! Kis cheez ka reminder chahiye?\n1. Birthday\n2. Anniversary")
    user_state[cid] = {}

@bot.message_handler(func=lambda m: True)
def handle_message(msg):
    cid, txt = msg.chat.id, msg.text.strip()
    state = user_state.get(cid, {})

    if not state:
        if txt in ["1","2"]:
            user_state[cid] = {"type": "Birthday" if txt=="1" else "Anniversary"}
            bot.send_message(cid, "Naam bataiye:")
        else:
            bot.send_message(cid, "Pehle choose karein:\n1. Birthday\n2. Anniversary")
    elif "name" not in state:
        state["name"] = txt
        bot.send_message(cid, "Date bataiye (DD-MM-YYYY ya 1 Jan 2000):")
    elif "date" not in state:
        try:
            dt = parser.parse(txt, dayfirst=True).date()
            state["date"] = dt.strftime("%d-%m-%Y")
            bot.send_message(cid, "Time bataiye (08:00 AM ya 07:30 PM):")
        except:
            bot.send_message(cid, "Date samajh nahi aaya. Dobara likhiye:")
    elif "time" not in state:
        try:
            tm = datetime.strptime(txt.upper(), "%I:%M %p").time()
            state["time"] = tm.strftime("%H:%M")
            add_to_google_sheet(cid, state["type"], state["name"], state["date"], state["time"])
            bot.send_message(cid, f"✅ Reminder saved for {state['name']} on {state['date']} at {txt.upper()}")
            user_state.pop(cid)
        except:
            bot.send_message(cid, "Time galat hai. Format: 08:00 AM ya 07:30 PM")
    else:
        bot.send_message(cid, "❌ Kuch galat hua, /start se shuru karein.")
        user_state.pop(cid, None)

# --- Launch ---
if __name__ == "__main__":
    threading.Thread(target=schedule_checker, daemon=True).start()
    bot.infinity_polling()
