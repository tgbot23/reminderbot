import os
import json
import telebot
import gspread
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ---- Constants ----
BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ---- Google Sheets Setup ----
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Convert JSON string to dictionary and use it
google_creds_dict = json.loads(GOOGLE_CREDS_JSON)
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Telegram reminders").sheet1

# ---- Reminder Check Function ----
def check_reminders():
    print("[Scheduler] Checking for due reminders...")
    data = sheet.get_all_records()
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    for row in data:
        if str(row.get("Notified")).strip().lower() == "yes":
            continue

        scheduled_time = str(row.get("DateTime")).strip()
        if scheduled_time == now:
            chat_id = str(row.get("ChatID")).strip()
            message = str(row.get("Message")).strip()
            bot.send_message(chat_id, f"⏰ Reminder: {message}")
            row_number = data.index(row) + 2
            sheet.update_cell(row_number, 5, "Yes")
            print(f"[✅] Reminder sent to {chat_id}")

# ---- Scheduler Setup ----
scheduler = BackgroundScheduler()
scheduler.add_job(check_reminders, trigger='interval', minutes=1)
scheduler.start()
print("✅ Scheduler thread started")

# ---- Webhook (for Flask) ----
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=["GET", "HEAD"])
def index():
    return "Bot is running", 200

# ---- Telegram Handlers ----
@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.reply_to(message, "Welcome! Send your reminder in this format:\n\n`Reminder message | yyyy-mm-dd hh:mm`", parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def reminder_handler(message):
    try:
        text = message.text
        if '|' not in text:
            bot.reply_to(message, "Invalid format. Use:\n`Message | yyyy-mm-dd hh:mm`", parse_mode="Markdown")
            return

        msg, dt = map(str.strip, text.split('|'))
        datetime.strptime(dt, "%Y-%m-%d %H:%M")  # Validate time

        sheet.append_row([message.chat.id, message.chat.first_name, msg, dt, ""])
        bot.reply_to(message, f"✅ Reminder set for {dt}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ---- Main ----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
