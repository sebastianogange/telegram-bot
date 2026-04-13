import telebot
import os
import time
import requests
import threading
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# 💰 BANKROLL
bankroll = 100
profit = 0
giocate = 0
max_giocate = 2

STOP_LOSS = -5
TAKE_PROFIT = 5

selected_matches = []
matches_state = {}
last_day = None

LEAGUES_ALLOWED = [39, 140, 135, 78, 61]

def send(msg):
    bot.send_message(CHAT_ID, msg)

# 🧠 xG
def calcola_xg(tiri, in_porta):
    return (tiri * 0.05) + (in_porta * 0.15)

def prob_goal(xg):
    if xg >= 1.5: return 80
    if xg >= 1.2: return 70
    if xg >= 1.0: return 60
    if xg >= 0.8: return 50
    return 30

# 💰 stake dinamico
def calcola_stake(prob):
    if prob >= 70:
        return round(bankroll * 0.015, 2)
    elif prob >= 50:
        return round(bankroll * 0.007, 2)
    return 0

# 📲 COMANDI TELEGRAM
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "🤖 Bot attivo\nUsa /status /profit /reset")

@bot.message_handler(commands=['status'])
def status(msg):
    bot.reply_to(msg, f"📊 Giocate: {giocate}\n💰 Profit: {profit}\n🏦 Bankroll: {bankroll}")

@bot.message_handler(commands=['profit'])
def profit_cmd(msg):
    bot.reply_to(msg, f"💰 Profit: {profit}")

@bot.message_handler(commands=['reset'])
def reset(msg):
    global profit, giocate, bankroll
    profit = 0
    giocate = 0
    bankroll = 100
    bot.reply_to(msg, "♻️ Reset completato")

# 📅 SELEZIONE PARTITE
def seleziona_partite():
    global selected_matches

    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    headers = {"x-apisports-key": API_KEY}

    try:
        data = requests.get(url, headers=headers).json()
    except:
        return

    matches = []

    for m in data.get("response", []):
        if m["league"]["id"] not in LEAGUES_ALLOWED:
            continue

        matches.append({
            "id": m["fixture"]["id"],
            "home": m["teams"]["home"]["name"],
            "away": m["teams"]["away"]["name"]
        })

    selected_matches = matches[:3]

    if not selected_matches:
        return

    msg = "📅 STRATEGIA GIORNALIERA\n\n"

    for i, m in enumerate(selected_matches):
        msg += f"""{i+1}) {m['home']} - {m['away']}

👉 Over 0.5 Primo Tempo
👉 Se 0-0 → Over 1.5 Secondo Tempo

\n"""

    send(msg)

# 🔴 LIVE
def check_matches():
    global giocate, profit, bankroll

    if profit <= STOP_LOSS:
        send("🛑 STOP LOSS raggiunto")
        return

    if profit >= TAKE_PROFIT:
        send("🎯 TAKE PROFIT raggiunto")
        return

    if giocate >= max_giocate:
        return

    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}

    try:
        data = requests.get(url, headers=headers).json()
    except:
        return

    for m in data.get("response", []):

        fid = m["fixture"]["id"]

        if fid not in [x["id"] for x in selected_matches]:
            continue

        minute = m["fixture"]["status"]["elapsed"]
        goals = (m["goals"]["home"] or 0) + (m["goals"]["away"] or 0)

        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]

        try:
            stats = m["statistics"][0]
            tiri = stats["shots"]["total"] or 0
            in_porta = stats["shots"]["on"] or 0
        except:
            continue

        xg = round(calcola_xg(tiri, in_porta), 2)
        prob = prob_goal(xg)

        if fid not in matches_state:
            matches_state[fid] = {"entered": False, "last_xg": xg}

        state = matches_state[fid]

        # ❌ partita morta
        if minute == 45 and goals == 0 and tiri < 6:
            send(f"❌ {home}-{away}\nNO BET")
            continue

        # 🔥 ingresso
        if 50 <= minute <= 60 and not state["entered"]:

            stake = calcola_stake(prob)

            if stake == 0:
                continue

            giocate += 1
            state["entered"] = True

            send(f"""⚽ {home}-{away}

⏱ {minute}'
📈 xG: {xg}
🤖 Prob: {prob}%

👉 GIOCA:
Over 1.5 Secondo Tempo

💰 Stake: {stake}
""")

        # 📊 risultato
        if state["entered"] and minute >= 90:

            stake = calcola_stake(prob)

            if goals >= 2:
                profit += stake
                bankroll += stake
                result = "✅ WIN"
            else:
                profit -= stake
                bankroll -= stake
                result = "❌ LOSS"

            send(f"""📊 RISULTATO

{home}-{away}
{result}

💰 Profit: {profit}
🏦 Bankroll: {bankroll}
""")

            state["entered"] = False

# 🔁 LOOP THREAD
def loop_live():
    global last_day

    while True:
        today = datetime.now().strftime("%Y-%m-%d")

        if last_day != today:
            seleziona_partite()
            last_day = today

        check_matches()
        time.sleep(60)

# ▶️ AVVIO
threading.Thread(target=loop_live).start()
bot.infinity_polling()
