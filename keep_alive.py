from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "🤖 Reminder Bot is running."

@app.route('/health')
def health():
    return "OK", 200

def keep_alive():
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT",5000)))).start()
