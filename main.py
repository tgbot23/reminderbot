import os
import json
import logging
from datetime import datetime
from dateutil import parser
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    JobQueue,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
TYPE, NAME, DATE, TIME = range(4)

# Timezone for IST
IST = pytz.timezone("Asia/Kolkata")

# Google Sheet helper functions
def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Telegram Reminders").sheet1
    return sheet

def add_to_google_sheet(chat_id, type_, name, date, time_):
    try:
        sheet = get_google_sheet()
        sheet.append_row([str(chat_id), type_, name, date, time_])
        logger.info(f"Added reminder to sheet: {name} {date} {time_}")
    except Exception as e:
        logger.error(f"Error adding to Google Sheet: {e}")

# Conversation handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Namaste! Kis cheez ka reminder chahiye?\n1. Birthday\n2. Anniversary"
    )
    return TYPE

async def type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "1":
        context.user_data["type"] = "Birthday"
    elif text == "2":
        context.user_data["type"] = "Anniversary"
    else:
        await update.message.reply_text("Please choose 1 for Birthday or 2 for Anniversary.")
        return TYPE
    await update.message.reply_text("Naam bataiye (jiska reminder chahiye):")
    return NAME

async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "Date bataiye Birthday/Shaadi ki (jaise: 01-01-2000 ya 1 Jan 2000):"
    )
    return DATE

async def date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        dob = parser.parse(text, dayfirst=True).date()
        context.user_data["date"] = dob.strftime("%d-%m-%Y")
        await update.message.reply_text(
            "Kitne baje reminder chahiye? (jaise: 08:00 AM ya 07:30 PM)"
        )
        return TIME
    except Exception:
        await update.message.reply_text(
            "❌ Date format samajh nahi aaya. Dobara likhein (01-01-2000 ya 1 Jan 2000)"
        )
        return DATE

async def time_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    try:
        user_time = datetime.strptime(text, "%I:%M %p").time()
        formatted_time = user_time.strftime("%H:%M")

        chat_id = update.effective_chat.id
        entry = {
            "chat_id": chat_id,
            "type": context.user_data["type"],
            "name": context.user_data["name"],
            "date": context.user_data["date"],
            "time": formatted_time,
        }

        add_to_google_sheet(
            entry["chat_id"], entry["type"], entry["name"], entry["date"], entry["time"]
        )

        await update.message.reply_text(
            f"✅ Reminder saved!\n{entry['type']} of {entry['name']} on {entry['date']} at {text}"
        )
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text(
            "❌ Time format galat hai. Please likhein: 08:00 AM ya 07:30 PM"
        )
        return TIME

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Reminder creation cancelled. /start se dobara try karein.")
    return ConversationHandler.END

# Reminder sending job
async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    try:
        now = datetime.now(IST)
        current_time = now.strftime("%H:%M")
        today = now.strftime("%d-%m")

        sheet = get_google_sheet()
        records = sheet.get_all_records()

        for entry in records:
            if entry.get("date", "")[:5] == today and entry.get("time", "") == current_time:
                years = now.year - int(entry["date"][-4:])
                if entry["type"] == "Birthday":
                    msg = f"🎂 Aaj {entry['name']} ka Birthday hai! {years} saal ke ho gaye hain. Mubarak ho!"
                else:
                    msg = f"💍 Aaj {entry['name']} ki shaadi ki {years}vi anniversary hai! Mubarak ho!"
                try:
                    await context.bot.send_message(int(entry["chat_id"]), msg)
                    logger.info(f"Reminder sent to {entry['name']} at {entry['chat_id']}")
                except Exception as e:
                    logger.error(f"Error sending reminder: {e}")
    except Exception as e:
        logger.error(f"Error in send_reminders job: {e}")

def main():
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        logger.error("BOT_TOKEN environment variable not set")
        return

    # Create JobQueue explicitly
    job_queue = JobQueue()

    application = ApplicationBuilder().token(TOKEN).job_queue(job_queue).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, type_handler)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_handler)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, time_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Schedule the reminders job every minute
    job_queue.run_repeating(send_reminders, interval=60, first=10)

    # Start the bot (this blocks and auto-reconnects)
    application.run_polling()

if __name__ == "__main__":
    main()
