import telebot
import os
import requests
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TOKEN)
tz = ZoneInfo("Europe/Rome")

LEAGUES = [
    39,140,135,78,61,94,88,203,144,207,
    119,71,62,79,141,136,103,98,
    2,3,848
]

last_chat_id = None
api_requests = 0

selected_matches = set()
tracked_matches = {}

# 💰 BANKROLL
bankroll = 100.0
bets = []

# ==============================
# UTILS
# ==============================
def normalize(text):
    return text.split('@')[0].strip().lower()

def send(msg):
    if last_chat_id:
        bot.send_message(last_chat_id, msg)

# ==============================
# API
# ==============================
def api_call(url):
    global api_requests

    headers = {
        "x-apisports-key": API_KEY,
        "x-rapidapi-host": "v3.football.api-sports.io"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        api_requests += 1
        return r.json()
    except:
        return {}

# ==============================
# PREMATCH
# ==============================
def selezione_pro():
    global selected_matches
    selected_matches.clear()

    today = datetime.now(tz).strftime("%Y-%m-%d")
    data = api_call(f"https://v3.football.api-sports.io/fixtures?date={today}")

    now = datetime.now(tz)
    scelte = []

    for m in data.get("response", []):
        try:
            if m["league"]["id"] not in LEAGUES:
                continue

            fixture_time = datetime.fromisoformat(
                m["fixture"]["date"].replace("Z","+00:00")
            ).astimezone(tz)

            if fixture_time <= now:
                continue

            if not (12 <= fixture_time.hour <= 23):
                continue

            scelte.append(m)

        except:
            continue

    msg = "🔥 PARTITE SELEZIONATE\n\n"

    for m in scelte[:3]:
        match_id = m["fixture"]["id"]
        selected_matches.add(match_id)
        msg += f"{m['teams']['home']['name']} - {m['teams']['away']['name']}\n"

    send(msg)

# ==============================
# STAT
# ==============================
def get_stat(stats, name):
    for s in stats:
        if s["type"] == name:
            return s["value"] or 0
    return 0

# ==============================
# LIVE SCAN
# ==============================
def live_scan():
    data = api_call("https://v3.football.api-sports.io/fixtures?live=all")

    for m in data.get("response", []):
        try:
            match_id = m["fixture"]["id"]

            if match_id not in selected_matches:
                continue

            if tracked_matches.get(match_id, {}).get("finished"):
                continue

            minute = m["fixture"]["status"]["elapsed"]
            g_home = m["goals"]["home"]
            g_away = m["goals"]["away"]
            total = g_home + g_away

            name = f"{m['teams']['home']['name']} - {m['teams']['away']['name']}"

            if match_id not in tracked_matches:
                tracked_matches[match_id] = {}

            state = tracked_matches[match_id]

            # HT
            if minute <= 45:
                if total >= 1 and not state.get("ht"):
                    bets.append({
                        "match": name,
                        "type": "HT",
                        "stake": 1,
                        "odds": 1.30,
                        "id": match_id,
                        "resolved": False
                    })
                    send(f"✅ OVER 0.5 HT\n{name}")
                    state["ht"] = True
                continue

            stats = m.get("statistics")
            if not stats:
                continue

            hs = stats[0]["statistics"]
            as_ = stats[1]["statistics"]

            xg = float(get_stat(hs,"Expected Goals (xG)")) + float(get_stat(as_,"Expected Goals (xG)"))
            shots = int(get_stat(hs,"Shots on Goal")) + int(get_stat(as_,"Shots on Goal"))
            attacks = int(get_stat(hs,"Dangerous Attacks")) + int(get_stat(as_,"Dangerous Attacks"))

            momentum = attacks + shots*2
            quality = xg / shots if shots > 0 else 0

            if total <= 1 and not state.get("st"):

                trigger = False

                if minute >= 60 and xg >= 1.2 and momentum >= 70 and shots >= 5:
                    trigger = True

                if 68 <= minute <= 75 and xg >= 1.6 and momentum >= 100 and shots >= 10:
                    trigger = True

                if quality < 0.08 or shots <= 2:
                    trigger = False

                if trigger:
                    bets.append({
                        "match": name,
                        "type": "ST",
                        "stake": 1.5,
                        "odds": 1.80,
                        "id": match_id,
                        "resolved": False
                    })

                    send(f"⚡ OVER 1.5 ST\n{name}")
                    state["st"] = True
                    state["finished"] = True

        except:
            continue

# ==============================
# RISULTATI
# ==============================
def check_results():
    global bankroll

    data = api_call("https://v3.football.api-sports.io/fixtures?live=all")

    for bet in bets:
        if bet["resolved"]:
            continue

        for m in data.get("response", []):
            if m["fixture"]["id"] != bet["id"]:
                continue

            if m["fixture"]["status"]["short"] == "FT":

                goals = m["goals"]["home"] + m["goals"]["away"]

                if bet["type"] == "HT":
                    win = goals >= 1
                else:
                    win = goals >= 2

                if win:
                    bankroll += bet["stake"] * (bet["odds"] - 1)
                else:
                    bankroll -= bet["stake"]

                bet["resolved"] = True

# ==============================
# LOOP
# ==============================
def loop():
    last_day = None

    while True:
        try:
            now = datetime.now(tz)

            if now.hour == 11 and 30 <= now.minute <= 35 and last_day != now.date():
                selezione_pro()
                last_day = now.date()

            live_scan()
            check_results()

            time.sleep(120)

        except:
            time.sleep(10)

# ==============================
# TELEGRAM
# ==============================
@bot.message_handler(func=lambda m: True)
def handle(msg):
    global last_chat_id, bankroll, bets

    last_chat_id = msg.chat.id
    text = normalize(msg.text)

    if text == "/start":
        bot.reply_to(msg, "🤖 BOT TRADER ATTIVO")

    elif text == "/bank":
        bot.reply_to(msg, f"💰 Bankroll: {round(bankroll,2)}")

    elif text == "/profit":
        profit = bankroll - 100
        bot.reply_to(msg, f"📈 Profit: {round(profit,2)}")

    elif text == "/roi":
        total_stake = sum(b["stake"] for b in bets if b["resolved"])
        profit = bankroll - 100
        roi = (profit / total_stake * 100) if total_stake > 0 else 0
        bot.reply_to(msg, f"📊 ROI: {round(roi,2)}%")

    elif text == "/bets":
        if not bets:
            bot.reply_to(msg, "Nessuna scommessa")
        else:
            txt = "\n".join([f"{b['match']} - {b['type']} - {b['stake']}" for b in bets])
            bot.reply_to(msg, txt)

    elif text == "/open":
        open_bets = [b for b in bets if not b["resolved"]]
        if not open_bets:
            bot.reply_to(msg, "Nessuna scommessa aperta")
        else:
            txt = "\n".join([f"{b['match']} - {b['type']}" for b in open_bets])
            bot.reply_to(msg, txt)

    elif text == "/reset":
        bankroll = 100
        bets = []
        bot.reply_to(msg, "🔄 Reset completato")

    elif text == "/oggi":
        selezione_pro()

    elif text == "/api":
        bot.reply_to(msg, f"API calls: {api_requests}")

# ==============================
# START
# ==============================
print("🚀 BOT TRADER FIXATO ATTIVO")

threading.Thread(target=loop, daemon=True).start()
bot.infinity_polling(skip_pending=True)
