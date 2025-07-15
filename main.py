import os
import logging
import time
from flask import Flask, request
from telebot import TeleBot, types
from apscheduler.schedulers.background import BackgroundScheduler
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ========== Logging setup ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== Environment Setup ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON")

# ========== Google Sheets Setup ==========
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS_JSON, scope)
client = gspread.authorize(creds)
sheet = client.open("Telegram reminders").sheet1

# ========== Bot Setup ==========
bot = TeleBot(BOT_TOKEN)
app = Flask(__name__)
scheduler = BackgroundScheduler()

# ========== Reminder Function ==========
def check_reminders():
    try:
        logger.info("🔁 Checking reminders...")
        records = sheet.get_all_records()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for row in records:
            name = row.get("Name")
            chat_id = row.get("ChatID")
            message = row.get("Message")
            reminder_time = row.get("DateTime")  # format: YYYY-MM-DD HH:MM
            sent = row.get("Sent")

            if reminder_time == now and str(sent).lower() != "yes":
                try:
                    logger.info(f"⏰ Sending reminder to {name} ({chat_id})")
                    bot.send_message(chat_id, f"🔔 Reminder: {message}")
                    sheet.update_cell(records.index(row) + 2, 5, "Yes")  # Column E = Sent
                    logger.info(f"✅ Sent and updated sheet for {name}")
                except Exception as e:
                    logger.error(f"❌ Failed to send reminder to {chat_id}: {e}")
        logger.info("✅ Reminder check complete.\n")
    except Exception as e:
        logger.error(f"🔥 Error checking reminders: {e}")

# ========== Scheduler Setup ==========
scheduler.add_job(check_reminders, 'interval', minutes=1)
scheduler.start()
logger.info("✅ Scheduler thread started")

# ========== Bot Handlers ==========
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "👋 Welcome! Send me your reminder in format:\n`YYYY-MM-DD HH:MM | Your message`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    try:
        text = message.text
        if "|" in text:
            dt, msg = map(str.strip, text.split("|", 1))
            datetime.strptime(dt, "%Y-%m-%d %H:%M")  # Validate format
            sheet.append_row([message.from_user.first_name, message.chat.id, msg, dt, "No"])
            bot.reply_to(message, "✅ Reminder set successfully.")
        else:
            bot.reply_to(message, "⚠️ Please send in correct format:\n`YYYY-MM-DD HH:MM | Message`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# ========== Flask Routes ==========
@app.route('/')
def index():
    return 'Bot is running!'

@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    update = types.Update.de_json(request.get_json())
    bot.process_new_updates([update])
    return 'ok'

# ========== Main Entrypoint ==========
if __name__ == '__main__':
    bot.remove_webhook()
    time.sleep(1)
    logger.info("📡 Removed existing webhook. Starting polling...")
    import threading
    threading.Thread(target=lambda: bot.infinity_polling(timeout=60, long_polling_timeout=10)).start()
    app.run(host='0.0.0.0', port=10000)
