import os

import dotenv
from telegram.ext import filters, ApplicationBuilder, CommandHandler, MessageHandler

import bot

dotenv.load_dotenv()

if __name__ == '__main__':
  application = ApplicationBuilder().token(
    token=os.environ.get('TELEGRAM_BOT_TOKEN')
  ).build()
  
  start_handler = CommandHandler('start', bot.start)
  application.add_handler(start_handler)

  chat_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), bot.chat)
  application.add_handler(chat_handler)
  
  application.run_polling()
