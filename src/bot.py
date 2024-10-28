import logging
import os

import dotenv
import telegram
from telegram.ext import filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler

dotenv.load_dotenv()

logging.basicConfig(
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
  level=logging.INFO
)

async def start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
  await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")
async def echo(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
  # 
  if update.message.is_topic_message:
    await context.bot.send_message(
      chat_id=update.effective_chat.id,
      message_thread_id=update.message.message_thread_id,
      text=update.message.text
    )
  else:
    await context.bot.create_forum_topic(chat_id=update.effective_chat.id, name=update.message.text)
    await context.bot.send_message(
      chat_id=update.effective_chat.id,
      text='topic created'
    )

if __name__ == '__main__':
  application = ApplicationBuilder().token(
    token=os.environ.get('TELEGRAM_BOT_TOKEN')
  ).build()
  
  start_handler = CommandHandler('start', start)
  application.add_handler(start_handler)

  echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)
  application.add_handler(echo_handler)
  
  application.run_polling()