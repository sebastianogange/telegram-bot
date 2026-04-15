import telebot
import os
import requests
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

# ==============================
# CONFIG
# ==============================
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TOKEN)

tz = ZoneInfo("Europe/Rome")

# ==============================
# STATO BOT
# ==============================
bankroll = 100.0
profit = 0.0
giocate = 0

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
def seleziona(chat_id):
    today = datetime.now(tz).strftime("%Y-%m-%d")

    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    data = api_call(url)

    matches = data.get("response", [])[:3]

    if not matches:
        bot.send_message(chat_id, "⚠️ Nessuna partita oggi")
        return

    msg = "📅 PARTITE OGGI\n\n"

    for m in matches:
        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]
        msg += f"{home} - {away}\n"

    bot.send_message(chat_id, msg)

# ==============================
# LOOP ORARIO
# ==============================
def loop(chat_id):
    last = None

    while True:
        now = datetime.now(tz)
        print("⏰ LOOP:", now)

        if now.hour == 11 and 30 <= now.minute <= 35 and last != now.date():
            print("🚀 INVIO PARTITE")
            seleziona(chat_id)
            last = now.date()

        time.sleep(60)

# ==============================
# COMANDI
# ==============================
@bot.message_handler(func=lambda m: True)
def handle(msg):
    global profit, bankroll, giocate

    text = msg.text.lower()

    print("📩 MSG:", text)

    if text == "/start":
        bot.reply_to(msg, "🤖 Bot attivo")

        # avvia loop dopo start
        threading.Thread(target=loop, args=(msg.chat.id,), daemon=True).start()

    elif text == "/profit":
        bot.reply_to(msg, f"💰 Profit: {profit}")

    elif text == "/status":
        bot.reply_to(msg, f"Giocate: {giocate} | Bankroll: {bankroll}")

    elif text == "/reset":
        profit = 0
        giocate = 0
        bankroll = 100
        bot.reply_to(msg, "Reset completato")

    elif text == "/api":
        bot.reply_to(msg, f"API: {api_requests}/{MAX_REQUESTS}")

    else:
        bot.reply_to(msg, f"Ricevuto: {text}")

# ==============================
# START BOT
# ==============================
print("🚀 BOT IN POLLING ATTIVO")
bot.infinity_polling(skip_pending=True)
