import telebot
import os
import requests
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request

# ==============================
# 🔑 CONFIG
# ==============================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
API_KEY = os.getenv("API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

tz = ZoneInfo("Europe/Rome")

# ==============================
# 📲 MENU COMANDI
# ==============================
bot.set_my_commands([
    telebot.types.BotCommand("start", "Avvia bot"),
    telebot.types.BotCommand("status", "Stato bot"),
    telebot.types.BotCommand("profit", "Profit"),
    telebot.types.BotCommand("api", "Uso API"),
    telebot.types.BotCommand("reset", "Reset sistema")
])

# ==============================
# 💰 BANKROLL
# ==============================
bankroll = 100.0
profit = 0.0
giocate = 0
max_giocate = 2

selected_matches = []

# ==============================
# 📡 API TRACKING
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
# 📩 SEND
# ==============================
def send(msg):
    try:
        bot.send_message(CHAT_ID, msg)
    except:
        pass

# ==============================
# 🧠 xG + PROB
# ==============================
def calcola_xg(tiri, porta):
    return (tiri * 0.05) + (porta * 0.15)

def prob_goal(xg):
    if xg >= 1.5: return 80
    if xg >= 1.2: return 70
    if xg >= 1.0: return 60
    if xg >= 0.8: return 50
    return 30

def stake(prob):
    if prob >= 70: return bankroll * 0.015
    if prob >= 50: return bankroll * 0.007
    return 0

# ==============================
# 🎯 CAMPIONATI
# ==============================
ALL_LEAGUES = [
    39,140,135,78,61,88,94,144,203,207,
    71,253,235,218,119,262,307,304,114,239
]

# ==============================
# 🧠 FILTRO STORICO
# ==============================
def filtra_leghe():
    migliori = []

    for league in ALL_LEAGUES:
        url = f"https://v3.football.api-sports.io/fixtures?league={league}&last=10"
        data = api_call(url)

        matches = data.get("response", [])
        if len(matches) < 10:
            continue

        goals = sum((m["goals"]["home"] or 0)+(m["goals"]["away"] or 0) for m in matches)
        media = goals / len(matches)

        if media >= 2.4:
            migliori.append(league)

    return migliori if migliori else ALL_LEAGUES[:5]

# ==============================
# 📅 SELEZIONE PARTITE
# ==============================
def seleziona():
    global selected_matches

    leagues = filtra_leghe()
    today = datetime.now(tz).strftime("%Y-%m-%d")

    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    data = api_call(url)

    matches = []

    for m in data.get("response", []):
        if m["league"]["id"] not in leagues:
            continue

        matches.append({
            "id": m["fixture"]["id"],
            "home": m["teams"]["home"]["name"],
            "away": m["teams"]["away"]["name"]
        })

    selected_matches = matches[:3]

    if not selected_matches:
        send("⚠️ Nessuna partita oggi")
        return

    msg = "📅 STRATEGIA OGGI\n\n"

    for i,m in enumerate(selected_matches):
        msg += f"{i+1}) {m['home']} - {m['away']}\n"
        msg += "👉 Over 0.5 HT\n👉 Se 0-0 → Over 1.5 2T\n\n"

    send(msg)

# ==============================
# 🔴 LIVE
# ==============================
def live():
    global giocate, profit, bankroll

    url = "https://v3.football.api-sports.io/fixtures?live=all"
    data = api_call(url)

    for m in data.get("response", []):

        if m["fixture"]["id"] not in [x["id"] for x in selected_matches]:
            continue

        minute = m["fixture"]["status"]["elapsed"]

        try:
            stats = m["statistics"][0]
            tiri = stats["shots"]["total"] or 0
            porta = stats["shots"]["on"] or 0
        except:
            continue

        xg = calcola_xg(tiri, porta)
        momentum = porta + tiri*0.5

        if 50 <= minute <= 60 and giocate < max_giocate:
            if xg >= 1.2 and momentum >= 8:

                p = prob_goal(xg)
                s = stake(p)

                giocate += 1

                send(f"""🔥 LIVE

⏱ {minute}'
📈 xG {round(xg,2)}
⚡ Momentum {momentum}

👉 Over 1.5 2T
💰 Stake {round(s,2)}""")

# ==============================
# 🔁 LOOP
# ==============================
def loop():
    last = None

    while True:
        now = datetime.now(tz)

        if now.hour == 11 and now.minute == 30 and last != now.date():
            seleziona()
            last = now.date()

        live()
        time.sleep(60)

# ==============================
# 🌐 WEBHOOK
# ==============================
@app.route('/', methods=['GET'])
def home():
    return "Bot attivo"

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "ok"

# ==============================
# 📲 COMANDI
# ==============================
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "🤖 BOT PRO ATTIVO")

@bot.message_handler(commands=['status'])
def status(msg):
    bot.reply_to(msg, f"""📊 STATO

Giocate: {giocate}
💰 Profit: {round(profit,2)}
🏦 Bankroll: {round(bankroll,2)}""")

@bot.message_handler(commands=['profit'])
def profit_cmd(msg):
    bot.reply_to(msg, f"""💰 PROFIT

Profit: {round(profit,2)}
Bankroll: {round(bankroll,2)}
Giocate: {giocate}""")

@bot.message_handler(commands=['api'])
def api(msg):
    perc = round((api_requests/MAX_REQUESTS)*100,1)
    bot.reply_to(msg, f"{api_requests}/{MAX_REQUESTS} ({perc}%)")

@bot.message_handler(commands=['reset'])
def reset(msg):
    global profit, giocate, bankroll
    profit = 0
    giocate = 0
    bankroll = 100
    bot.reply_to(msg, "♻️ Reset completato")

# ==============================
# ▶️ START
# ==============================
if __name__ == "__main__":

    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook")
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}/{TELEGRAM_TOKEN}")

    threading.Thread(target=loop).start()

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
