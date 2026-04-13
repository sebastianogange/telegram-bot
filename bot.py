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

# 🎯 10 campionati
ALL_LEAGUES = [39,140,135,78,61,88,94,144,203,207]

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

# 💰 stake
def calcola_stake(prob):
    if prob >= 70:
        return round(bankroll * 0.015, 2)
    elif prob >= 50:
        return round(bankroll * 0.007, 2)
    return 0

# 🧠 AUTO FILTRO CAMPIONATI
def filtra_campionati():
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    headers = {"x-apisports-key": API_KEY}

    try:
        data = requests.get(url, headers=headers).json()
    except:
        return ALL_LEAGUES

    league_stats = {}

    for m in data.get("response", []):
        league = m["league"]["id"]

        if league not in ALL_LEAGUES:
            continue

        goals = (m["goals"]["home"] or 0) + (m["goals"]["away"] or 0)

        if league not in league_stats:
            league_stats[league] = {"matches":0,"goals":0}

        league_stats[league]["matches"] += 1
        league_stats[league]["goals"] += goals

    migliori = []

    for l, stats in league_stats.items():
        if stats["matches"] < 3:
            continue

        media = stats["goals"] / stats["matches"]

        if media >= 2.2:
            migliori.append(l)

    if not migliori:
        return ALL_LEAGUES[:5]

    return migliori

# 📅 selezione partite
def seleziona_partite():
    global selected_matches

    leagues = filtra_campionati()

    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    headers = {"x-apisports-key": API_KEY}

    try:
        data = requests.get(url, headers=headers).json()
    except:
        return

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

    msg = "📅 STRATEGIA + AUTO FILTRO\n\n"

    msg += f"Campionati attivi: {len(leagues)}\n\n"

    for i, m in enumerate(selected_matches):
        msg += f"""{i+1}) {m['home']} - {m['away']}

👉 Over 0.5 HT
👉 Se 0-0 → Over 1.5 2T

\n"""

    send(msg)

# 🔴 LIVE
def check_matches():
    global giocate, profit, bankroll

    if profit <= STOP_LOSS:
        send("🛑 STOP LOSS")
        return

    if profit >= TAKE_PROFIT:
        send("🎯 TAKE PROFIT")
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
            matches_state[fid] = {"entered": False}

        state = matches_state[fid]

        if minute == 45 and goals == 0 and tiri < 6:
            send(f"❌ {home}-{away} NO BET")
            continue

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

👉 Over 1.5 Secondo Tempo

💰 Stake: {stake}
""")

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

# 🔁 LOOP
def loop_live():
    global last_day

    while True:
        today = datetime.now().strftime("%Y-%m-%d")

        if last_day != today:
            seleziona_partite()
            last_day = today

        check_matches()
        time.sleep(60)

threading.Thread(target=loop_live).start()
bot.infinity_polling()
