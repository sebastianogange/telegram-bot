import requests
import time
import telegram
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

bot = telegram.Bot(token=TELEGRAM_TOKEN)

def send_message(msg):
    bot.send_message(chat_id=CHAT_ID, text=msg)

def calcola_IA(tiri, in_porta, corner):
    IA = 0
    if tiri >= 10:
        IA += 1
    if in_porta >= 4:
        IA += 1
    if corner >= 5:
        IA += 1
    return IA

def check_matches():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}
    res = requests.get(url, headers=headers).json()

    for match in res["response"]:
        minuto = match["fixture"]["status"]["elapsed"]
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        goals_home = match["goals"]["home"]
        goals_away = match["goals"]["away"]

        if minuto == 45 and goals_home == 0 and goals_away == 0:
            try:
                stats = match["statistics"][0]
                tiri = stats["shots"]["total"]
                in_porta = stats["shots"]["on"]
                corner = stats["corners"]
            except:
                continue

            IA = calcola_IA(tiri, in_porta, corner)

            if IA >= 3:
                segnale = "🟢 ENTRA ORA"
            elif IA == 2:
                segnale = "🟡 ENTRA RIDOTTO"
            else:
                segnale = "🔴 NON ENTRARE"

            msg = f"""⚽ {home} - {away}
⏱ 0-0 HT

Tiri: {tiri}
In porta: {in_porta}
Corner: {corner}

{segnale}
"""
            send_message(msg)

while True:
    check_matches()
    time.sleep(60)
