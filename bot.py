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

print("DEBUG API_KEY:", API_KEY)

if not API_KEY:
    print("❌ API KEY NON CARICATA")

bot = telebot.TeleBot(TOKEN)
tz = ZoneInfo("Europe/Rome")

# ==============================
# 21 COMPETIZIONI EUROPEE
# ==============================
LEAGUES = [
    # TOP 5
    39, 140, 135, 78, 61,

    # ALTRI CAMPIONATI
    94, 88, 203, 144, 207,
    119, 71, 62, 79, 141,
    136, 103, 98,

    # COPPE EUROPEE
    2,   # Champions League
    3,   # Europa League
    848  # Conference League
]

# ==============================
# STATO
# ==============================
last_chat_id = None
loop_started = False
api_requests = 0

profit = 0
bankroll = 100
giocate = 0

# ==============================
# CACHE
# ==============================
cache = {}
team_cache = {}
sent_matches = set()

CACHE_TIME = 300
MAX_REQUESTS = 7000

# ==============================
# API CALL OTTIMIZZATA
# ==============================
def api_call(url):
    global api_requests

    now = time.time()

    if url in cache:
        data, timestamp = cache[url]
        if now - timestamp < CACHE_TIME:
            return data

    if api_requests > MAX_REQUESTS:
        print("🚫 LIMITE API RAGGIUNTO")
        return {}

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

    except Exception as e:
        print("API DOWN:", e)
        return {}

# ==============================
# SEND
# ==============================
def send(msg):
    if last_chat_id:
        bot.send_message(last_chat_id, msg)

# ==============================
# STATS SQUADRA
# ==============================
def get_team_stats(team_id):
    if team_id in team_cache:
        return team_cache[team_id]

    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10"
    data = api_call(url)

    matches = data.get("response", [])

    if not matches:
        return {"gf": 0, "ga": 0, "over": 0}

    gf = ga = over = 0

    for m in matches:
        home = m["teams"]["home"]["id"] == team_id

        g1 = m["goals"]["home"] if home else m["goals"]["away"]
        g2 = m["goals"]["away"] if home else m["goals"]["home"]

        gf += g1
        ga += g2

        if g1 + g2 >= 3:
            over += 1

    tot = len(matches)

    stats = {
        "gf": gf / tot,
        "ga": ga / tot,
        "over": over / tot
    }

    team_cache[team_id] = stats
    return stats

# ==============================
# PRE MATCH (EUROPA + COPPE)
# ==============================
def selezione_pro():
    today = datetime.now(tz).strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    data = api_call(url)

    scelte = []

    for m in data.get("response", [])[:25]:
        try:
            league_id = m["league"]["id"]

            if league_id not in LEAGUES:
                continue

            home_id = m["teams"]["home"]["id"]
            away_id = m["teams"]["away"]["id"]

            h = get_team_stats(home_id)
            a = get_team_stats(away_id)

            media = h["gf"] + a["gf"]
            over = (h["over"] + a["over"]) / 2

            # 🔥 filtro più severo per coppe
            if league_id in [2, 3, 848]:
                if media < 2.8 or over < 0.65:
                    continue

            if media >= 2.5 and over >= 0.6:
                scelte.append(
                    f"{m['teams']['home']['name']} - {m['teams']['away']['name']}"
                )

        except:
            continue

    if not scelte:
        send("⚠️ Nessuna partita PRO Europa")
        return

    msg = "🔥 PRE MATCH PRO (EUROPA + COPPE)\n\n"

    for s in scelte[:3]:
        msg += s + "\n"

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
# LIVE
# ==============================
def live_scan():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    data = api_call(url)

    for m in data.get("response", []):
        try:
            match_id = m["fixture"]["id"]

            if match_id in sent_matches:
                continue

            stats = m.get("statistics")
            if not stats:
                continue

            home_stats = stats[0]["statistics"]
            away_stats = stats[1]["statistics"]

            xg = float(get_stat(home_stats, "Expected Goals (xG)")) + \
                 float(get_stat(away_stats, "Expected Goals (xG)"))

            momentum = int(get_stat(home_stats, "Dangerous Attacks")) + \
                       int(get_stat(away_stats, "Dangerous Attacks"))

            shots = int(get_stat(home_stats, "Shots on Goal")) + \
                    int(get_stat(away_stats, "Shots on Goal"))

            if xg >= 1.5 and momentum >= 80 and shots >= 6:
                send(f"""⚡ LIVE ALERT

{m['teams']['home']['name']} - {m['teams']['away']['name']}

xG: {xg}
Momentum: {momentum}
Tiri: {shots}
""")
                sent_matches.add(match_id)

        except:
            continue

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

        time.sleep(180)

# ==============================
# COMANDI
# ==============================
@bot.message_handler(func=lambda m: True)
def handle(msg):
    global last_chat_id, loop_started, profit, bankroll, giocate

    last_chat_id = msg.chat.id
    text = msg.text.lower() if msg.text else ""

    if text.startswith("/start"):
        bot.reply_to(msg, "🤖 BOT PRO EUROPA + COPPE ATTIVO")

        if not loop_started:
            threading.Thread(target=loop, daemon=True).start()
            loop_started = True

    elif text.startswith("/profit"):
        bot.reply_to(msg, f"💰 Profit: {profit}")

    elif text.startswith("/status"):
        bot.reply_to(msg, f"""📊 STATO

Bankroll: {bankroll}
Profit: {profit}
Giocate: {giocate}
""")

    elif text.startswith("/reset"):
        profit = 0
        bankroll = 100
        giocate = 0
        bot.reply_to(msg, "♻️ Reset completato")

    elif text.startswith("/oggi"):
        selezione_pro()

    elif text.startswith("/api"):
        bot.reply_to(msg, f"API calls: {api_requests}")

# ==============================
# START
# ==============================
print("🚀 BOT EUROPA + COPPE ATTIVO")

bot.infinity_polling(skip_pending=True, none_stop=True)
