import telebot
import os

TELEGRAM_TOKEN = os.getenv("8609230078:AAFCoriuwxzpAheNQMKZWZYbttR7aD_NUk")
CHAT_ID = int(os.getenv("168842957"))

bot = telebot.TeleBot(TELEGRAM_TOKEN)

bot.send_message(CHAT_ID, "✅ TEST OK - BOT FUNZIONA")

while True:
    pass
