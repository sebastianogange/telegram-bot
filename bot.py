import telebot
import os

TOKEN = os.getenv("TELEGRAM_TOKEN")

bot = telebot.TeleBot(TOKEN)

# ==============================
# STATO BOT
# ==============================
bankroll = 100.0
profit = 0.0
giocate = 0

api_requests = 0
MAX_REQUESTS = 7500

# ==============================
# HANDLER
# ==============================
@bot.message_handler(func=lambda m: True)
def handle(msg):
    global profit, bankroll, giocate, api_requests

    text = msg.text.lower() if msg.text else ""

    print("📩 MSG:", text)

    # rimuove eventuale @nomebot
    if "@" in text:
        text = text.split("@")[0]

    # ======================
    # COMANDI
    # ======================

    if text.startswith("/start"):
        bot.reply_to(msg, "🤖 Bot attivo")

    elif text.startswith("/profit"):
        bot.reply_to(msg, f"💰 Profit: {profit}")

    elif text.startswith("/status"):
        bot.reply_to(msg, f"""📊 STATO

Giocate: {giocate}
Bankroll: {bankroll}
Profit: {profit}
""")

    elif text.startswith("/reset"):
        profit = 0
        giocate = 0
        bankroll = 100
        bot.reply_to(msg, "♻️ Reset completato")

    elif text.startswith("/api"):
        bot.reply_to(msg, f"API: {api_requests}/{MAX_REQUESTS}")

    else:
        bot.reply_to(msg, f"Ricevuto: {text}")

# ==============================
# START
# ==============================
print("🚀 BOT ATTIVO")
while True:
    try:
        print("🚀 BOT ATTIVO")
        bot.infinity_polling(skip_pending=True, none_stop=True)
    except Exception as e:
        print("ERRORE:", e)
        time.sleep(5)
