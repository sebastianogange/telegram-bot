import telebot
import os
import requests
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request

# ==============================
# CONFIG
# ==============================
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

tz = ZoneInfo("Europe/Rome")

# ==============================
# STATO BOT
# ==============================
bankroll = 100.0
profit = 0.0
giocate = 0

last_chat_id = None

# ==============================
# SEND
# ==============================
def send(msg):
    global last_chat_id
    if last_chat_id:
        bot.send_message(last_chat_id, msg)

# ==============================
# API
# ==============================
api_requests = 0
MAX_REQUESTS = 7500

def api_call(url):
    global api_requests
    headers = {"x-apisports-key": API_KEY}
    try:
        r = requests.get(url, headers=headers)
        api_requests += 1
        return r.json()
    except:
        return {}

# ==============================
# SELEZIONE PARTITE
# ==============================
def seleziona():
    print("🚀 INVIO PARTITE")

    today = datetime.now(tz).strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    data = api_call(url)

    matches = data.get("response", [])[:3]

    if not matches:
        send("⚠️ Nessuna partita oggi")
        return

    msg = "📅 PARTITE OGGI\n\n"

    for m in matches:
        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]
        msg += f"{home} - {away}\n"

    send(msg)

# ==============================
# LOOP (FIX ORARIO)
# ==============================
def loop():
    last = None

    while True:
        now = datetime.now(tz)
        print("⏰ LOOP:", now)

        if now.hour == 11 and 30 <= now.minute <= 35 and last != now.date():
            seleziona()
            last = now.date()

        time.sleep(60)

# ==============================
# WEBHOOK (DEFINITIVO)
# ==============================
@app.route('/', methods=['GET'])
def home():
    return "Bot attivo"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    global profit, bankroll, giocate, last_chat_id

    data = request.get_json()

    print("📦 RAW:", data)

    if not data:
        return '', 200

    message = data.get("message") or data.get("edited_message")

    if not message:
        return '', 200

    chat_id = message["chat"]["id"]
    last_chat_id = chat_id

    text = message.get("text", "")

    print("📩 MSG:", text)

    if not text:
        return '', 200

    text = text.lower().strip()

    # ======================
    # DEBUG BASE
    # ======================
    bot.send_message(chat_id, f"DEBUG: {text}")

    # ======================
    # COMANDI
    # ======================

    if text.startswith("/start"):
        bot.send_message(chat_id, "🤖 Bot attivo")

    elif text.startswith("/profit"):
        bot.send_message(chat_id, f"💰 Profit: {profit}")

    elif text.startswith("/status"):
        bot.send_message(chat_id, f"Giocate: {giocate} | Bankroll: {bankroll}")

    elif text.startswith("/reset"):
        profit = 0
        giocate = 0
        bankroll = 100
        bot.send_message(chat_id, "Reset completato")

    elif text.startswith("/api"):
        bot.send_message(chat_id, f"API: {api_requests}/{MAX_REQUESTS}")

    return '', 200

# ==============================
# START
# ==============================
if __name__ == "__main__":

    # reset webhook
    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")

    # set webhook
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}/{TOKEN}")

    # loop
    threading.Thread(target=loop, daemon=True).start()

    # server
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False)
