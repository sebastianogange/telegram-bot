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

api_requests = 0
MAX_REQUESTS = 7500

last_chat_id = None
loop_started = False  # ✅ evita duplicazione loop

# ==============================
# API
# ==============================
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
# INVIO MESSAGGI
# ==============================
def send(msg):
    global last_chat_id
    if last_chat_id:
        bot.send_message(last_chat_id, msg)

# ==============================
# SELEZIONE PARTITE
# ==============================
def seleziona():
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
# LOOP ORARIO
# ==============================
def loop():
    last = None

    while True:
        now = datetime.now(tz)
        print("⏰ LOOP:", now)

        if now.hour == 11 and 30 <= now.minute <= 35 and last != now.date():
            print("🚀 INVIO PARTITE")
            seleziona()
            last = now.date()

        time.sleep(60)

# ==============================
# COMANDI
# ==============================
@bot.message_handler(func=lambda m: True)
def handle(msg):
    global profit, bankroll, giocate, last_chat_id, loop_started

    last_chat_id = msg.chat.id

    text = msg.text.lower() if msg.text else ""

    print("📩 MSG:", text)

    # rimuove @nomebot
    if "@" in text:
        text = text.split("@")[0]

    if text.startswith("/start"):
        bot.reply_to(msg, "🤖 Bot attivo")

        # ✅ avvia loop UNA SOLA VOLTA
        if not loop_started:
            threading.Thread(target=loop, daemon=True).start()
            loop_started = True

    elif text.startswith("/profit"):
        bot.reply_to(msg, f"💰 Profit: {profit}")

    elif text.startswith("/status"):
        bot.reply_to(msg, f"""📊 STATO

Giocate: {giocate}
Bankroll: {bankroll}
Profit: {profit}
""")

    elif text.startswith("/reset"):
        profit = 0
        giocate = 0
        bankroll = 100
        bot.reply_to(msg, "♻️ Reset completato")

    elif text.startswith("/api"):
        bot.reply_to(msg, f"API: {api_requests}/{MAX_REQUESTS}")

    else:
        bot.reply_to(msg, f"Ricevuto: {text}")

# ==============================
# START
# ==============================
print("🚀 BOT STABILE ATTIVO")

bot.infinity_polling(skip_pending=True, none_stop=True)
