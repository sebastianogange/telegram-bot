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
# LEAGUES
# ==============================
LEAGUES = [
    39,140,135,78,61,94,88,203,144,207,
    119,71,62,79,141,136,103,98,
    2,3,848
]

# ==============================
# STATO
# ==============================
last_chat_id = None
api_requests = 0
selected_matches = set()
tracked_matches = {}
bets = {}

profit = 0
bankroll = 100
giocate = 0

# ==============================
# CACHE (NO LIVE)
# ==============================
cache = {}
CACHE_TIME = 300

# ==============================
# SAFE TELEGRAM
# ==============================
def send(msg):
    global last_chat_id
    if not last_chat_id:
        return

    for i in range(3):
        try:
            bot.send_message(last_chat_id, msg)
            return
        except Exception as e:
            print(f"❌ TELEGRAM ERROR (retry {i+1}):", e)
            time.sleep(2)

def safe_reply(msg, text):
    for i in range(3):
        try:
            bot.reply_to(msg, text)
            return
        except Exception as e:
            print(f"❌ REPLY ERROR (retry {i+1}):", e)
            time.sleep(2)

# ==============================
# API CALL (NO CACHE LIVE)
# ==============================
def api_call(url):
    global api_requests
    now = time.time()

    if "live" not in url:
        if url in cache:
            data, t = cache[url]
            if now - t < CACHE_TIME:
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

        if "live" not in url:
            cache[url] = (data, now)

        return data

    except Exception as e:
        print("❌ API ERROR:", e)
        return {}

# ==============================
# TEAM STATS
# ==============================
def get_team_stats(team_id):
    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10"
    data = api_call(url)

    matches = data.get("response", [])
    if not matches:
        return {"gf":0,"over":0}

    gf = over = 0

    for m in matches:
        home = m["teams"]["home"]["id"] == team_id
        g1 = m["goals"]["home"] if home else m["goals"]["away"]
        g2 = m["goals"]["away"] if home else m["goals"]["home"]

        gf += g1
        if g1+g2 >=3:
            over +=1

    tot = len(matches)
    return {"gf":gf/tot,"over":over/tot}

# ==============================
# PREMATCH 11:30
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

            if media >= 2.3 and over >= 0.55:
                scelte.append((m, media))

        except:
            continue

    scelte = sorted(scelte, key=lambda x:x[1], reverse=True)

    msg = "🔥 PARTITE SELEZIONATE\n\n"

    for m,_ in scelte[:3]:
        match_id = m["fixture"]["id"]
        selected_matches.add(match_id)
        msg += f"{m['teams']['home']['name']} - {m['teams']['away']['name']}\n"

    send(msg)

# ==============================
# LIVE
# ==============================
def get_stat(stats, name):
    for s in stats:
        if s["type"] == name:
            return s["value"] or 0
    return 0

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
                tracked_matches[match_id] = {"finished":False}

            # HT
            if minute <=45 and total >=1:
                if not tracked_matches[match_id].get("ht"):
                    send(f"✅ OVER 0.5 HT\n{name}")
                    tracked_matches[match_id]["finished"] = True
                    tracked_matches[match_id]["ht"] = True
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

            # ST
            if minute >=60 and total <=1:

                trigger = False

                if xg>=1.2 and momentum>=70 and shots>=5:
                    trigger=True
                elif momentum>=100:
                    trigger=True

                if shots<=2:
                    trigger=False

                if trigger:
                    send(f"⚡ OVER 1.5 ST\n{name}")

                tracked_matches[match_id]["finished"] = True

        except Exception as e:
            print("LIVE ERROR:", e)

# ==============================
# LOOP STABILE
# ==============================
def loop():
    last_day = None

    while True:
        try:
            now = datetime.now(tz)

            print("🔄 LOOP ATTIVO", now)

            if now.hour == 11 and 30 <= now.minute <= 35 and last_day != now.date():
                selezione_pro()
                last_day = now.date()

            if 12 <= now.hour <= 23:
                live_scan()

            time.sleep(180)

        except Exception as e:
            print("❌ LOOP ERROR:", e)
            time.sleep(10)

# ==============================
# TELEGRAM
# ==============================
@bot.message_handler(func=lambda m: True)
def handle(msg):
    global last_chat_id
    last_chat_id = msg.chat.id
    text = msg.text.lower()

    if text.startswith("/start"):
        safe_reply(msg,"🤖 BOT ATTIVO")

    elif text.startswith("/oggi"):
        selezione_pro()

    elif text.startswith("/api"):
        safe_reply(msg, f"API calls: {api_requests}")

# ==============================
# START
# ==============================
print("🚀 BOT STABILE ATTIVO")

threading.Thread(target=loop, daemon=True).start()

bot.infinity_polling(skip_pending=True, none_stop=True)
