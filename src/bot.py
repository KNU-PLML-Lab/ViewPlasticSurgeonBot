import asyncio
import logging
import os
import time
from collections import deque
from typing import Optional

import dotenv
import telegram
from telegram.ext import ContextTypes

import lm
import db

dotenv.load_dotenv()



class ThrottledTelegramChat:
  def __init__(
    self,
    min_update_interval: float = 1.0,  # 메시지 업데이트 최소 간격(초)
    batch_size: int = 20,  # 한 번에 모을 최대 토큰 수
  ):
    self.min_update_interval = min_update_interval
    self.batch_size = batch_size
    self.message_buffer = deque()
    self.last_update_time = 0

  async def process_stream(
    self,
    chat_stream,
    update: telegram.Update,
    context: ContextTypes.DEFAULT_TYPE,
    initial_message: Optional[str] = None,
  ):
    # 초기 메시지 전송
    message = await context.bot.send_message(
      chat_id=update.effective_chat.id,
      message_thread_id=update.message.message_thread_id,
      text=initial_message or "...",
      # parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
    )

    current_text = ""
    
    async def update_message():
      try:
        await context.bot.edit_message_text(
          chat_id=update.effective_chat.id,
          message_id=message.message_id,
          # message_thread_id=update.message.message_thread_id,
          text=current_text,
          # parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
        )
        self.last_update_time = time.time()
      except telegram.error.RetryAfter as e:
        # Rate limit에 걸린 경우 대기
        await asyncio.sleep(e.retry_after)
        await update_message()
      except Exception as e:
        print(f"메시지 업데이트 중 오류 발생: {e}")

    try:
      for chunk in chat_stream:
        if chunk:
          # escape  '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!' 
          # chunk = chunk.replace('_', '\\_').replace('**', '*').replace('[', '\\[').replace(']', '\\]')\
          #   .replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`')\
          #   .replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-')\
          #   .replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}')\
          #   .replace('.', '\\.').replace('!', '\\!')
          current_text += chunk
          self.message_buffer.append(chunk)

          # 버퍼가 batch_size를 넘거나, 마지막 업데이트로부터 min_update_interval이 지난 경우
          current_time = time.time()
          if (len(self.message_buffer) >= self.batch_size or 
            (current_time - self.last_update_time) >= self.min_update_interval):
            
            # 버퍼 비우기
            self.message_buffer.clear()
            
            # 마지막 업데이트로부터 충분한 시간이 지났는지 확인
            time_since_last_update = current_time - self.last_update_time
            if time_since_last_update < self.min_update_interval:
              await asyncio.sleep(self.min_update_interval - time_since_last_update)
            
            await update_message()

      # 스트림이 종료된 후 최종 업데이트
      if self.message_buffer:
        await update_message()
        return current_text

    except Exception as e:
      print(f"스트리밍 처리 중 오류 발생: {e}")
      # 오류 발생 시 최종 상태 업데이트
      await update_message()
      return current_text



logging.basicConfig(
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
  level=logging.INFO
)

lm_instance = lm.VpsbLmServer2()

async def start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
  # await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")
  pass
async def echo(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
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

async def chat_single_private(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
  if update.effective_chat == None:
    print('No effective_chat')
    return
  elif update.effective_user == None:
    print('No effective_user')
    return
  elif update.message == None:
    print('No message')
    return
  
  # *** 채팅 정보 분석
  user_id = update.effective_user.id # is equal to chat_id
  # user_username = update.effective_user.username
  user_name = update.effective_user.full_name
  date_str = str(update.message.date)
  chat_text = update.message.text

  # 관리 정보 가져오기
  room_info = db.room_info.get_row_from_user_id(user_id)
  # 새 채팅이면
  if room_info == None:
    new_room = await context.bot.create_forum_topic(chat_id=int(os.environ.get('TELEGRAM_ADMIN_FORUM_GROUP_ID')), name=user_name)
    forum_id = new_room.message_thread_id
    db.room_info.insert_row(user_id, forum_id)
    room_info = {
      'user_id': user_id,
      'admin_forum_id': forum_id
    }
  
  # 메시지 관리자에게 전달 및 저장
  db.room_chats.insert_row(user_id, 'user', chat_text, date_str)
  await update.message.forward(
    chat_id=int(os.environ.get('TELEGRAM_ADMIN_FORUM_GROUP_ID')),
    message_thread_id=room_info['admin_forum_id']
  )

  # *** 챗봇 채팅 생성 프로세스
  # 텍스트 채팅이 아니면 무시...
  if not chat_text:
    return
  # 마지막 채팅들 가져오기
  chat_history = db.build_history(db.room_chats.get_last_rows_from_user_id(user_id, 10))
  chat_history.append({
    'role': 'user',
    'content': chat_text,
  })
  
  # 스트림 생성 요청
  chat_stream = lm_instance.chat_stream(chat_history)
  throttled_chat = ThrottledTelegramChat(
    min_update_interval=1.0,  # 1초마다 업데이트
    batch_size=20,  # 20개의 토큰이 모이면 업데이트
  )
  assistant_message = await throttled_chat.process_stream(
    chat_stream,
    update,
    context,
    initial_message="..."
  )

  # *** 채팅 기록 저장
  db.room_chats.insert_row(user_id, 'assistant', assistant_message, date_str)
  # 관리자 기록 저장
  await context.bot.send_message(
    chat_id=int(os.environ.get('TELEGRAM_ADMIN_FORUM_GROUP_ID')),
    message_thread_id=room_info['admin_forum_id'],
    text=assistant_message
  )
