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
# STATO
# ==============================
last_chat_id = None
loop_started = False
api_requests = 0

# ==============================
# API
# ==============================
def api_call(url):
    global api_requests
    headers = {"x-apisports-key": API_KEY}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        api_requests += 1

        if r.status_code != 200:
            print("❌ API ERROR:", r.status_code)
            return {}

        return r.json()

    except Exception as e:
        print("❌ API DOWN:", e)
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
    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10"
    data = api_call(url)

    matches = data.get("response", [])

    if not matches:
        return {"gf": 0, "ga": 0, "over": 0}

    gf = ga = over = 0

    for m in matches:
        home = m["teams"]["home"]["id"] == team_id

        if home:
            g1 = m["goals"]["home"]
            g2 = m["goals"]["away"]
        else:
            g1 = m["goals"]["away"]
            g2 = m["goals"]["home"]

        gf += g1
        ga += g2

        if g1 + g2 >= 3:
            over += 1

    tot = len(matches)

    return {
        "gf": gf / tot,
        "ga": ga / tot,
        "over": over / tot
    }

# ==============================
# PRE MATCH (PRO)
# ==============================
def selezione_pro():
    today = datetime.now(tz).strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    data = api_call(url)

    scelte = []

    for m in data.get("response", []):
        home_id = m["teams"]["home"]["id"]
        away_id = m["teams"]["away"]["id"]

        h = get_team_stats(home_id)
        a = get_team_stats(away_id)

        media = h["gf"] + a["gf"]
        over = (h["over"] + a["over"]) / 2

        if media >= 2.5 and over >= 0.6:
            scelte.append(
                f"{m['teams']['home']['name']} - {m['teams']['away']['name']}"
            )

    if not scelte:
        send("⚠️ Nessuna partita PRO")
        return

    msg = "🔥 PRE MATCH PRO (18:30)\n\n"

    for s in scelte[:5]:
        msg += s + "\n"

    send(msg)

# ==============================
# LIVE + MOMENTUM
# ==============================
def live_scan():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    data = api_call(url)

    for m in data.get("response", []):
        try:
            stats = m["statistics"]

            home_stats = stats[0]["statistics"]
            away_stats = stats[1]["statistics"]

            xg_home = home_stats[2]["value"] or 0
            xg_away = away_stats[2]["value"] or 0

            att_home = home_stats[13]["value"] or 0
            att_away = away_stats[13]["value"] or 0

            shots_home = home_stats[0]["value"] or 0
            shots_away = away_stats[0]["value"] or 0

            xg_total = float(xg_home) + float(xg_away)
            momentum = att_home + att_away
            shots = shots_home + shots_away

            if xg_total >= 1.5 and momentum >= 80 and shots >= 6:
                send(f"""⚡ LIVE ALERT

{m['teams']['home']['name']} - {m['teams']['away']['name']}

xG: {xg_total}
Momentum: {momentum}
Tiri: {shots}
""")

        except:
            continue

# ==============================
# LOOP
# ==============================
def loop():
    last_day = None

    while True:
        now = datetime.now(tz)

        # 🔥 SOLO 18:30
        if now.hour == 18 and 30 <= now.minute <= 35 and last_day != now.date():
            print("🚀 INVIO PRE MATCH 18:30")
            selezione_pro()
            last_day = now.date()

        # LIVE ogni 60 sec
        live_scan()

        time.sleep(60)

# ==============================
# COMANDI
# ==============================
@bot.message_handler(func=lambda m: True)
def handle(msg):
    global last_chat_id, loop_started

    last_chat_id = msg.chat.id
    text = msg.text.lower() if msg.text else ""

    if "@" in text:
        text = text.split("@")[0]

    if text.startswith("/start"):
        bot.reply_to(msg, "🤖 BOT PRO ATTIVO (18:30 + LIVE)")

        if not loop_started:
            threading.Thread(target=loop, daemon=True).start()
            loop_started = True

    elif text.startswith("/oggi"):
        selezione_pro()

    elif text.startswith("/live"):
        live_scan()

    elif text.startswith("/api"):
        bot.reply_to(msg, f"API used: {api_requests}")

# ==============================
# START
# ==============================
print("🚀 BOT PRO LIVE ATTIVO (18:30)")

bot.infinity_polling(skip_pending=True, none_stop=True)
