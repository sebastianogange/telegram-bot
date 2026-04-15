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
# COMPETIZIONI EUROPEE
# ==============================
LEAGUES = [
    39, 140, 135, 78, 61,
    94, 88, 203, 144, 207,
    119, 71, 62, 79, 141,
    136, 103, 98,
    2, 3, 848
]

# ==============================
# STATO
# ==============================
last_chat_id = None
loop_started = False
api_requests = 0

selected_matches = set()
tracked_matches = {}

profit = 0.0
bankroll = 100.0
giocate = 0
bets = {}

# ==============================
# CACHE
# ==============================
cache = {}
team_cache = {}
CACHE_TIME = 300

# ==============================
# API CALL
# ==============================
def api_call(url):
    global api_requests
    now = time.time()

    if url in cache:
        data, timestamp = cache[url]
        if now - timestamp < CACHE_TIME:
            return data

    headers = {
        "x-apisports-key": API_KEY,
        "x-rapidapi-host": "v3.football.api-sports.io"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        api_requests += 1

        if r.status_code != 200:
            print("API ERROR:", r.status_code)
            return {}

        data = r.json()
        cache[url] = (data, now)
        return data

    except:
        return {}

# ==============================
# SEND
# ==============================
def send(msg):
    if last_chat_id:
        bot.send_message(last_chat_id, msg)

# ==============================
# TEAM STATS
# ==============================
def get_team_stats(team_id):
    if team_id in team_cache:
        return team_cache[team_id]

    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10"
    data = api_call(url)

    matches = data.get("response", [])

    if not matches:
        return {"gf": 0, "over": 0}

    gf = over = 0

    for m in matches:
        home = m["teams"]["home"]["id"] == team_id

        g1 = m["goals"]["home"] if home else m["goals"]["away"]
        g2 = m["goals"]["away"] if home else m["goals"]["home"]

        gf += g1
        if g1 + g2 >= 3:
            over += 1

    tot = len(matches)

    stats = {
        "gf": gf / tot,
        "over": over / tot
    }

    team_cache[team_id] = stats
    return stats

# ==============================
# PRE MATCH
# ==============================
def selezione_pro():
    global selected_matches

    selected_matches.clear()

    today = datetime.now(tz).strftime("%Y-%m-%d")
    data = api_call(f"https://v3.football.api-sports.io/fixtures?date={today}")

    scelte = []

    for m in data.get("response", []):
        try:
            if m["league"]["id"] not in LEAGUES:
                continue

            h = get_team_stats(m["teams"]["home"]["id"])
            a = get_team_stats(m["teams"]["away"]["id"])

            media = h["gf"] + a["gf"]
            over = (h["over"] + a["over"]) / 2

            if m["league"]["id"] in [2,3,848]:
                if media < 2.6 or over < 0.6:
                    continue

            if media >= 2.3 and over >= 0.55:
                scelte.append((m, media))

        except:
            continue

    scelte = sorted(scelte, key=lambda x: x[1], reverse=True)

    if not scelte:
        send("⚠️ Nessuna partita selezionata")
        return

    msg = "🔥 PARTITE SELEZIONATE\n\n"

    for m, _ in scelte[:3]:
        match_id = m["fixture"]["id"]
        selected_matches.add(match_id)
        msg += f"{m['teams']['home']['name']} - {m['teams']['away']['name']}\n"

    send(msg)

# ==============================
# STAT SAFE
# ==============================
def get_stat(stats, name):
    for s in stats:
        if s["type"] == name:
            return s["value"] or 0
    return 0

# ==============================
# LIVE SCAN (PRO)
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
            goals_home = m["goals"]["home"]
            goals_away = m["goals"]["away"]
            total_goals = goals_home + goals_away

            match_name = f"{m['teams']['home']['name']} - {m['teams']['away']['name']}"

            if match_id not in tracked_matches:
                tracked_matches[match_id] = {"finished": False}

            # ==============================
            # HT (FIX)
            # ==============================
            if minute <= 45 and total_goals >= 1:

                if not tracked_matches[match_id].get("ht_alert_sent"):

                    send(f"""✅ OVER 0.5 HT IN CASSA

{match_name}
Minuto: {minute}
Risultato: {goals_home}-{goals_away}
""")

                    bets[match_id] = {
                        "type": "HT",
                        "stake": 1,
                        "odds": 1.80,
                        "result_checked": False
                    }

                    tracked_matches[match_id]["finished"] = True
                    tracked_matches[match_id]["ht_alert_sent"] = True

                continue

            # ==============================
            # STATISTICHE
            # ==============================
            stats = m.get("statistics")
            if not stats:
                continue

            home_stats = stats[0]["statistics"]
            away_stats = stats[1]["statistics"]

            xg = float(get_stat(home_stats, "Expected Goals (xG)")) + \
                 float(get_stat(away_stats, "Expected Goals (xG)"))

            attacks = int(get_stat(home_stats, "Dangerous Attacks")) + \
                      int(get_stat(away_stats, "Dangerous Attacks"))

            shots = int(get_stat(home_stats, "Shots on Goal")) + \
                    int(get_stat(away_stats, "Shots on Goal"))

            # 🔥 MOMENTUM AVANZATO
            momentum = attacks + (shots * 2)

            # ==============================
            # FILTRO INTELLIGENTE PRO
            # ==============================
            if minute >= 60 and total_goals == 0:

                trigger = False

                # livello 1
                if xg >= 1.2 and momentum >= 70 and shots >= 5:
                    trigger = True

                # livello 2
                elif xg == 0 and momentum >= 80 and shots >= 6:
                    trigger = True

                # livello 3
                elif momentum >= 100:
                    trigger = True

                # blocco fake
                if shots <= 2:
                    trigger = False

                if trigger:
                    send(f"""⚡ OVER 1.5 SECONDO TEMPO

{match_name}

Minuto: {minute}
xG: {xg}
Momentum: {momentum}
Tiri: {shots}
""")

                    bets[match_id] = {
                        "type": "ST",
                        "stake": 1,
                        "odds": 1.90,
                        "result_checked": False
                    }

                tracked_matches[match_id]["finished"] = True

        except Exception as e:
            print("LIVE ERROR:", e)
            continue

# ==============================
# CHECK RISULTATI
# ==============================
def check_results():
    global profit, bankroll, giocate

    for match_id, bet in bets.items():

        if bet["result_checked"]:
            continue

        data = api_call(f"https://v3.football.api-sports.io/fixtures?id={match_id}")
        response = data.get("response", [])

        if not response:
            continue

        m = response[0]
        status = m["fixture"]["status"]["short"]

        if status not in ["FT", "AET", "PEN"]:
            continue

        goals = m["goals"]["home"] + m["goals"]["away"]

        win = False

        if bet["type"] == "HT":
            win = True
        elif bet["type"] == "ST":
            if goals >= 1:
                win = True

        if win:
            gain = bet["stake"] * (bet["odds"] - 1)
            profit += gain
            bankroll += gain
        else:
            profit -= bet["stake"]
            bankroll -= bet["stake"]

        giocate += 1
        bet["result_checked"] = True

# ==============================
# LOOP
# ==============================
def loop():
    last_day = None

    while True:
        now = datetime.now(tz)

        if now.hour == 18 and 30 <= now.minute <= 35 and last_day != now.date():
            selezione_pro()
            last_day = now.date()

        if 12 <= now.hour <= 23:
            live_scan()
            check_results()

        time.sleep(180)

# ==============================
# TELEGRAM
# ==============================
@bot.message_handler(func=lambda m: True)
def handle(msg):
    global last_chat_id, loop_started

    last_chat_id = msg.chat.id
    text = msg.text.lower() if msg.text else ""

    if text.startswith("/start"):
        bot.reply_to(msg, "🤖 BOT PRO ATTIVO")

        if not loop_started:
            threading.Thread(target=loop, daemon=True).start()
            loop_started = True

    elif text.startswith("/oggi"):
        selezione_pro()

    elif text.startswith("/profit"):
        bot.reply_to(msg, f"💰 Profit: {round(profit,2)}")

    elif text.startswith("/status"):
        bot.reply_to(msg, f"""📊 STATO

Bankroll: {round(bankroll,2)}
Profit: {round(profit,2)}
Giocate: {giocate}
""")

    elif text.startswith("/api"):
        bot.reply_to(msg, f"API calls: {api_requests}")

# ==============================
# START
# ==============================
print("🚀 BOT PRO DEFINITIVO ATTIVO")

bot.infinity_polling(skip_pending=True, none_stop=True)
