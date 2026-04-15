import telebot
import os

TOKEN = os.getenv("TELEGRAM_TOKEN")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(func=lambda m: True)
def echo(msg):
    print("MSG:", msg.text)
    bot.reply_to(msg, f"Ricevuto: {msg.text}")

print("BOT AVVIATO")
bot.infinity_polling()
