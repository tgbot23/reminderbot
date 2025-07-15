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
user_state = {}

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

# --- Reminder Check ---
def send_reminders():
    now = datetime.now(IST)
    print("⏰ Checking reminders at", now.strftime("%Y-%m-%d %H:%M:%S"))
    try:
        sheet = get_google_sheet()
        for e in sheet.get_all_records():
            try:
                dt = parser.parse(f"{e['date']} {e['time']}", dayfirst=True).replace(tzinfo=IST)
                diff = abs((now - dt).total_seconds())
                if diff < 180:
                    years = now.year - int(e['date'][-4:])
                    msg = (f"🎂 Aaj {e['name']} ka Birthday hai! {years} saal ke ho gaye hain. Mubarak ho!"
                           if e['type'] == "Birthday"
                           else f"💍 Aaj {e['name']} ki shaadi ki {years}vi anniversary hai! Mubarak ho!")
                    bot.send_message(int(e["chat_id"]), msg)
                    print("✅ Sent:", msg)
            except Exception as ex:
                print("⚠️ Error processing entry:", ex)
    except Exception as e:
        print("❌ Reminder Error:", e)

def schedule_checker():
    print("✅ Scheduler thread started")
    schedule.every().minute.do(send_reminders)
    while True:
        schedule.run_pending()
        time.sleep(1)

# --- Telegram Conversation Flow ---
@bot.message_handler(commands=['start'])
def handle_start(msg):
    cid = msg.chat.id
    bot.send_message(cid, "Namaste! Kis cheez ka reminder chahiye?\n1. Birthday\n2. Anniversary")
    user_state[cid] = {}

@bot.message_handler(func=lambda m: True)
def handle_message(msg):
    cid = msg.chat.id
    txt = msg.text.strip()
    state = user_state.get(cid, {})

    if not state:
        if txt in ["1", "2"]:
            user_state[cid] = {"type": "Birthday" if txt == "1" else "Anniversary"}
            bot.send_message(cid, "Naam bataiye (jiska reminder chahiye):")
        else:
            bot.send_message(cid, "Pehle choose karein:\n1. Birthday\n2. Anniversary")
    elif "type" in state and "name" not in state:
        state["name"] = txt
        bot.send_message(cid, "Date bataiye Birthday/Shaadi ki (jaise: 01-01-2000 ya 1 Jan 2000):")
    elif "name" in state and "date" not in state:
        try:
            dt = parser.parse(txt, dayfirst=True).date()
            state["date"] = dt.strftime("%d-%m-%Y")
            bot.send_message(cid, "Kitne baje reminder chahiye? (jaise: 08:00 AM ya 07:30 PM)")
        except:
            bot.send_message(cid, "❌ Date format samajh nahi aaya. Dobara likhein (01-01-2000 ya 1 Jan 2000)")
    elif "date" in state and "time" not in state:
        try:
            tm = datetime.strptime(txt.upper(), "%I:%M %p").time()
            state["time"] = tm.strftime("%H:%M")
            add_to_google_sheet(cid, state["type"], state["name"], state["date"], state["time"])
            bot.send_message(cid, f"✅ Reminder saved!\n{state['type']} of {state['name']} on {state['date']} at {txt.upper()}")
            user_state.pop(cid, None)
        except:
            bot.send_message(cid, "❌ Time format galat hai. Please likhein: 08:00 AM ya 07:30 PM")
    else:
        bot.send_message(cid, "❌ Galat input. /start se dobara shuru karein.")
        user_state.pop(cid, None)

# --- Launch Everything ---
if __name__ == "__main__":
    threading.Thread(target=schedule_checker).start()
    threading.Thread(target=bot.infinity_polling).start()
    keep_alive()
    port = int(os.environ.get("PORT", 5000))
    print("🌐 Flask running on port", port)
    app.run(host="0.0.0.0", port=port)
