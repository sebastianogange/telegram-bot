import telebot
import os
import time
import requests
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

# 🔑 CONFIG
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# 📲 REGISTRA COMANDI TELEGRAM
bot.set_my_commands([
    telebot.types.BotCommand("start", "Avvia il bot"),
    telebot.types.BotCommand("status", "Stato bot"),
    telebot.types.BotCommand("profit", "Profit attuale"),
    telebot.types.BotCommand("api", "Utilizzo API"),
    telebot.types.BotCommand("reset", "Reset sistema")
])

tz = ZoneInfo("Europe/Rome")

# 💰 BANKROLL
bankroll = 100.0
profit = 0.0
giocate = 0
max_giocate = 2

STOP_LOSS = -5
TAKE_PROFIT = 5

selected_matches = []
matches_state = {}
last_day_sent = None

# 📡 API TRACKING
api_requests = 0
last_reset_day = None
MAX_REQUESTS = 7500

# 🎯 20 CAMPIONATI
ALL_LEAGUES = [
    39, 140, 135, 78, 61,
    88, 94, 144, 203, 207,
    71, 253, 235, 218,
    119, 262, 307, 304,
    114, 239
]

# ==============================
# 📩 SEND
# ==============================
def send(msg):
    try:
        bot.send_message(CHAT_ID, msg)
    except Exception as e:
        print("Errore invio:", e)

# ==============================
# 📡 API WRAPPER
# ==============================
def api_call(url):
    global api_requests

    headers = {"x-apisports-key": API_KEY}

    try:
        response = requests.get(url, headers=headers)
        api_requests += 1

        if api_requests >= MAX_REQUESTS * 0.8:
            send(f"⚠️ API usage alto: {api_requests}/{MAX_REQUESTS}")

        return response.json()

    except Exception as e:
        print("Errore API:", e)
        return {}

# ==============================
# 🔄 RESET API
# ==============================
def reset_requests():
    global api_requests, last_reset_day

    today = datetime.now(tz).strftime("%Y-%m-%d")

    if last_reset_day != today:
        api_requests = 0
        last_reset_day = today

# ==============================
# 🧠 xG
# ==============================
def calcola_xg(tiri, in_porta):
    return (tiri * 0.05) + (in_porta * 0.15)

def prob_goal(xg):
    if xg >= 1.5: return 80
    if xg >= 1.2: return 70
    if xg >= 1.0: return 60
    if xg >= 0.8: return 50
    return 30

# ==============================
# 💰 STAKE
# ==============================
def calcola_stake(prob):
    global bankroll

    if prob >= 70:
        return round(bankroll * 0.015, 2)
    elif prob >= 50:
        return round(bankroll * 0.007, 2)

    return 0

# ==============================
# 📲 COMANDI
# ==============================
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "🤖 Bot attivo")

@bot.message_handler(commands=['status'])
def status(msg):
    bot.reply_to(msg, f"""📊 Giocate: {giocate}
💰 Profit: {profit}
🏦 Bankroll: {bankroll}""")

@bot.message_handler(commands=['profit'])
def profit_cmd(msg):
    bot.reply_to(msg, f"""💰 Profit: {profit}
🏦 Bankroll: {bankroll}
📊 Giocate: {giocate}""")

@bot.message_handler(commands=['api'])
def api_status(msg):
    percent = round((api_requests / MAX_REQUESTS) * 100, 1)

    bot.reply_to(msg, f"""📡 API USAGE

Richieste: {api_requests}/{MAX_REQUESTS}
Utilizzo: {percent}%
""")

@bot.message_handler(commands=['reset'])
def reset(msg):
    global profit, giocate, bankroll
    profit = 0
    giocate = 0
    bankroll = 100
    bot.reply_to(msg, "♻️ Reset completato")

# ==============================
# 🧠 FILTRO STORICO
# ==============================
def filtra_campionati_storico():
    migliori = []
    debug_msg = "📊 DEBUG STORICO\n\n"

    for league in ALL_LEAGUES:

        url = f"https://v3.football.api-sports.io/fixtures?league={league}&last=10"
        data = api_call(url)

        matches = data.get("response", [])

        if len(matches) < 10:
            continue

        goals = sum((m["goals"]["home"] or 0) + (m["goals"]["away"] or 0) for m in matches)

        media = round(goals / len(matches), 2)

        valido = media >= 2.4
        status = "✅" if valido else "❌"

        debug_msg += f"Lega {league} → {media} {status}\n"

        if valido:
            migliori.append(league)

    send(debug_msg)

    if not migliori:
        send("⚠️ Nessun campionato valido")
        return ALL_LEAGUES[:5]

    return migliori

# ==============================
# 📅 SELEZIONE PARTITE
# ==============================
def seleziona_partite():
    global selected_matches

    leagues = filtra_campionati_storico()

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
        send("⚠️ Nessuna partita selezionata")
        return

    msg = "📅 STRATEGIA PRO\n\n"

    for i, m in enumerate(selected_matches):
        msg += f"""{i+1}) {m['home']} - {m['away']}

👉 Over 0.5 HT
👉 Se 0-0 → Over 1.5 2T

\n"""

    send(msg)

# ==============================
# 🔴 LIVE
# ==============================
def check_matches():
    global giocate

    url = "https://v3.football.api-sports.io/fixtures?live=all"
    data = api_call(url)

    for m in data.get("response", []):

        fid = m["fixture"]["id"]

        if fid not in [x["id"] for x in selected_matches]:
            continue

        minute = m["fixture"]["status"]["elapsed"]

        try:
            stats = m["statistics"][0]
            tiri = stats["shots"]["total"] or 0
            in_porta = stats["shots"]["on"] or 0
        except:
            continue

        xg = calcola_xg(tiri, in_porta)
        momentum = in_porta + (tiri * 0.5)

        if 50 <= minute <= 60 and giocate < max_giocate:

            if xg >= 1.2 and momentum >= 8:

                prob = prob_goal(xg)
                stake = calcola_stake(prob)

                giocate += 1

                send(f"""🔥 LIVE ENTRY

⏱ {minute}'
📈 xG: {round(xg,2)}
⚡ Momentum: {momentum}

👉 Over 1.5 2T
💰 Stake: {stake}
""")

# ==============================
# 🔁 LOOP
# ==============================
def loop_live():
    global last_day_sent

    while True:
        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")

        reset_requests()

        if now.hour == 11 and now.minute == 30 and last_day_sent != today:
            seleziona_partite()
            last_day_sent = today

        check_matches()
        time.sleep(60)

# ▶️ AVVIO THREAD
threading.Thread(target=loop_live).start()

print("✅ BOT PRO ATTIVO")

# 🔁 POLLING SICURO (ANTI-ERROR 409)
while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        print("Errore polling:", e)
        time.sleep(5)
