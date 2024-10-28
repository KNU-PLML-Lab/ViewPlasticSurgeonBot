import logging
import os

import telegram
from telegram.ext import ContextTypes

import lm



logging.basicConfig(
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
  level=logging.INFO
)

lm_instance = lm.VpsbLmServer2()

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

async def chat(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
  res_text = lm_instance.chat_text([
    {"role": "user", "content": update.message.text}
  ])
  await context.bot.send_message(
    chat_id=update.effective_chat.id,
    message_thread_id=update.message.message_thread_id,
    text=res_text
  )
