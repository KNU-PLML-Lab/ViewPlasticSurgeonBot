import os

import dotenv
from telegram.ext import filters, ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler

import bot

dotenv.load_dotenv()

if __name__ == '__main__':
  application = ApplicationBuilder().token(
    token=os.environ.get('TELEGRAM_BOT_TOKEN')
  ).build()
  
  start_handler = CommandHandler('start', bot.start)
  application.add_handler(start_handler)
  
  # chat_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), bot.chat_single_private)
  chat_handler = MessageHandler(filters.ChatType.PRIVATE, bot.chat_single_private)
  application.add_handler(chat_handler)

  admin_handler = MessageHandler(~filters.ChatType.PRIVATE, bot.admin_group_chat)
  application.add_handler(admin_handler)

  admin_callback_handle = CallbackQueryHandler(bot.admin_callback)
  application.add_handler(admin_callback_handle)
  
  application.run_polling()
