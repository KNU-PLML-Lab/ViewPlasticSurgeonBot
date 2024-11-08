import re
import sqlite3
import os
import time
import random
from typing import List, Dict, Any, Generator, Tuple
import json

from tqdm import tqdm

def safe_key_string(key: str) -> str:
  # change non-alphanumeric characters to _
  key = re.sub(r'[^a-zA-Z0-9]', '_', key)
  # add _ if key has leading numbers
  if re.match(r'^[0-9]', key):
    key = '_' + key
  return key

class Sqlite3Db:
  def __init__(self, db_file: str):
    self.conn = sqlite3.connect(db_file)

    self._db_file = db_file

  def close(self, commit: bool = True):
    if hasattr(self, 'conn'):
      if commit:
        try:
          self.conn.commit()
        except:
          pass
      self.conn.close()

  def __del__(self):
    self.close()

  @staticmethod
  def ensure_safe_key_string(key: str) -> str:
    return safe_key_string(key)

  def table_list(self) -> List[str]:
    cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    # Remove default table like sqlite_sequence, ...
    return [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite')]

  def has_table(self, table_name: str) -> bool:
    table_name = Sqlite3Db.ensure_safe_key_string(table_name)
    cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='{}'".format(table_name))
    return len(cursor.fetchall()) > 0
  
  def get_table_keys(self, table_name: str) -> List[str]:
    table_name = Sqlite3Db.ensure_safe_key_string(table_name)
    self.conn.execute("SELECT * FROM {} LIMIT 0".format(table_name))
    return [description[0] for description in self.conn.description]

  def db_safe_insert_many_tuple(self, table_name: str, rows: List[Tuple[Any, ...]]) -> None:
    # New cursor for transaction
    cur = self.conn.cursor()
    cur.execute('BEGIN TRANSACTION')
    # Insert parameteried query
    retry_count = 0
    while True:
      try:
        cur.executemany('INSERT INTO {} VALUES ({})'.format(
          Sqlite3Db.ensure_safe_key_string(table_name),
          ",".join(["?"] * len(rows[0]))
        ), rows)
        cur.execute('COMMIT')
        cur.close()
        break
      except sqlite3.OperationalError as e:
        if 'database is locked' in str(e) and retry_count < self.max_retry:
          retry_count += 1
          print('🔒 Database is locked, retrying... ({} / {})'.format(retry_count, self.max_retry))
          # sleep random time between 0.1 and 0.5 seconds
          time.sleep(0.1 + 0.4 * random.random())
        else:
          # Rollback transaction
          cur.execute('ROLLBACK')
          cur.close()
          raise e

# Abstract class for sqlite3 table
class Sqlite3Table:
  def __init__(self, sqlite3db: Sqlite3Db, table_name: str):
    self.max_retry = 100
    
    self._db = sqlite3db
    self._table_name = Sqlite3Db.ensure_safe_key_string(table_name)
    self._init_db()
  
  def __str__(self) -> str:
    return f'{self.__class__.__name__}({self._db._db_file}#{self._table_name})'

  def _init_db(self) -> None:
    # Implement example
    # self._db.cur.execute('CREATE TABLE IF NOT EXISTS {} (key TEXT, value TEXT)'.format(self._table_name))
    # self._db.cur.execute('CREATE INDEX IF NOT EXISTS {}_key ON {} (key)'.format(self._table_name, self._table_name))
    raise NotImplementedError
  
  def tuple_to_dict(self, row: Tuple[Any, ...]) -> Dict[str, Any]:
    # Implement example
    # return {
    #   'key': row[0],
    #   'value': row[1]
    # }
    raise NotImplementedError
  
  def ensure_keys(self, keys: List[str]) -> bool:
    # Ensure all keys are in the table
    cursor = self._db.conn.cursor()
    cursor.execute('SELECT * FROM {} LIMIT 0'.format(self._table_name))
    table_columns = [description[0] for description in cursor.description]
    for key in keys:
      if key not in table_columns:
        return False
    return True
  
  def count(self) -> int:
    cursor = self._db.conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM {}'.format(self._table_name))
    return cursor.fetchone()[0]

  def safe_insert_many_tuple(self, rows: List[Tuple[Any, ...]]) -> None:
    # New cursor for transaction
    cur = self._db.conn.cursor()
    cur.execute('BEGIN TRANSACTION')
    # Insert parameteried query
    retry_count = 0
    while True:
      try:
        cur.executemany('INSERT INTO {} VALUES ({})'.format(
          self._table_name,
          ",".join(["?"] * len(rows[0]))
        ), rows)
        cur.execute('COMMIT')
        cur.close()
        break
      except sqlite3.OperationalError as e:
        if 'database is locked' in str(e) and retry_count < self.max_retry:
          retry_count += 1
          print('🔒 Database is locked, retrying... ({} / {})'.format(retry_count, self.max_retry))
          # sleep random time between 0.1 and 0.5 seconds
          time.sleep(0.1 + 0.4 * random.random())
        else:
          # Rollback transaction
          cur.execute('ROLLBACK')
          cur.close()
          raise e
        
  def safe_insert_many_dict(self, rows: List[Dict[str, Any]]) -> None:
    # Ensure all keys are in the table
    keys = set()
    for row in rows:
      keys.update(row.keys())
    if not self.ensure_keys(keys):
      raise Exception('Keys are not in the table (db: {}/ key: {})'.format(self._table_name, keys))

    # New cursor for transaction
    cur = self._db.conn.cursor()
    cur.execute('BEGIN TRANSACTION')
    # Insert parameteried query
    retry_count = 0
    while True:
      try:
        cur.executemany('INSERT INTO {} ({}) VALUES ({})'.format(
          self._table_name,
          ",".join(rows[0].keys()),
          ",".join(["?"] * len(rows[0]))
        ), [tuple(row.values()) for row in rows])
        cur.execute('COMMIT')
        cur.close()
        break
      except sqlite3.OperationalError as e:
        if 'database is locked' in str(e) and retry_count < self.max_retry:
          retry_count += 1
          print('🔒 Database is locked, retrying... (try: {} / {})'.format(retry_count, self.max_retry))
          # sleep random time between 0.1 and 0.5 seconds
          time.sleep(0.1 + 0.4 * random.random())
        else:
          # Rollback transaction
          cur.execute('ROLLBACK')
          cur.close()
          raise e
  
  def cursor_reader_tuple(self, batch_size: int = 1000) -> Generator[List[Tuple[Any, ...]], None, None]:
    # New cursor for transaction
    cur = self._db.conn.cursor()
    cur.execute('SELECT * FROM {}'.format(self._table_name))
    # Read batch
    while True:
      rows = cur.fetchmany(batch_size)
      if not rows:
        break
      yield rows
    # Close cursor
    cur.close()

  def cursor_reader_dict(self, batch_size: int = 1000) -> Generator[List[Dict[str, Any]], None, None]:
    # New cursor for transaction
    cur = self._db.conn.cursor()
    cur.execute('SELECT * FROM {}'.format(self._table_name))
    # Read batch
    while True:
      rows = cur.fetchmany(batch_size)
      if not rows:
        break
      yield [self.tuple_to_dict(row) for row in rows]
    # Close cursor
    cur.close()

class Sqlite3Utils:
  # Merge db_to_merge into db_to_merge_into (db_to_merge_into will be modified)
  @staticmethod
  def merge_db(db_to_merge_into: Sqlite3Db, db_to_merge: Sqlite3Db) -> None:
    # Merge tables
    for table_name in tqdm(db_to_merge.table_list(), desc='🗃️ Merging tables'):
      # Check keys if table exists
      if db_to_merge_into.has_table(table_name):
        keys_to_merge = db_to_merge.get_table_keys(table_name)
        keys_to_merge_into = db_to_merge_into.get_table_keys(table_name)
        if keys_to_merge != keys_to_merge_into:
          raise Exception('Keys are not matched (table: {}/ keys: {} vs {})'.format(
            table_name,
            keys_to_merge,
            keys_to_merge_into
          ))
      # Create table if not exists
      elif not db_to_merge_into.has_table(table_name):
        db_to_merge_into.conn.execute('CREATE TABLE {} AS SELECT * FROM {}'.format(
          table_name,
          table_name
        ))
      # Insert rows with tqdm
      for rows in tqdm(
        db_to_merge.cursor_reader_tuple(table_name),
        desc='📖 Reading rows from {}'.format(table_name),
        leave=False
      ):
        db_to_merge_into.db_safe_insert_many_tuple(table_name, rows)

class Sqlite3TableRoomInfo(Sqlite3Table):
  def _init_db(self) -> None:
    self._db.conn.execute(
      'CREATE TABLE IF NOT EXISTS {} (\
      user_id INTEGER PRIMARY KEY,\
      admin_forum_id INTEGER\
      )'.format(self._table_name)
    )
    self._db.conn.execute(
      'CREATE INDEX IF NOT EXISTS {}_user_id ON {} (user_id)'.format(self._table_name, self._table_name)
    )

  def tuple_to_dict(self, row: Tuple[Any, ...]) -> Dict[str, Any]:
    return {
      'user_id': row[0],
      'admin_forum_id': row[1],
    }
  
  def get_row_from_user_id(self, user_id: int) -> Dict[str, Any]:
    cursor = self._db.conn.cursor()
    cursor.execute('SELECT * FROM {} WHERE user_id=?'.format(self._table_name), (user_id,))
    row = cursor.fetchone()
    if row is None:
      return None
    return self.tuple_to_dict(row)
  
  def get_row_from_admin_forum_id(self, admin_forum_id: int) -> Dict[str, Any]:
    cursor = self._db.conn.cursor()
    cursor.execute('SELECT * FROM {} WHERE admin_forum_id=?'.format(self._table_name), (admin_forum_id,))
    row = cursor.fetchone()
    if row is None:
      return None
    return self.tuple_to_dict(row)

  def insert_row(self, user_id: int, admin_forum_id: int) -> None:
    self.safe_insert_many_tuple([(user_id, admin_forum_id)])

class Sqlite3TableRoomChats(Sqlite3Table):
  def _init_db(self) -> None:
    # sender: 'user' or 'assistant'
    self._db.conn.execute(
      'CREATE TABLE IF NOT EXISTS {} (\
      id INTEGER PRIMARY KEY AUTOINCREMENT,\
      user_id INTEGER,\
      sender TEXT,\
      message TEXT,\
      date TEXT\
      )'.format(self._table_name)
    )

  # def safe_insert_many_tuple(self, rows: List[Tuple[Any, ...]]) -> None:
  #   # New cursor for transaction
  #   cur = self._db.conn.cursor()
  #   cur.execute('BEGIN TRANSACTION')
  #   # Insert parameteried query
  #   retry_count = 0
  #   while True:
  #     try:
  #       cur.executemany('INSERT INTO {} VALUES (user_id, sender, message, date)'.format(
  #         self._table_name
  #       ), rows)
  #       cur.execute('COMMIT')
  #       cur.close()
  #       break
  #     except sqlite3.OperationalError as e:
  #       if 'database is locked' in str(e) and retry_count < self.max_retry:
  #         retry_count += 1
  #         print('🔒 Database is locked, retrying... ({} / {})'.format(retry_count, self.max_retry))
  #         # sleep random time between 0.1 and 0.5 seconds
  #         time.sleep(0.1 + 0.4 * random.random())
  #       else:
  #         # Rollback transaction
  #         cur.execute('ROLLBACK')
  #         cur.close()
  #         raise e

  def tuple_to_dict(self, row: Tuple[Any, ...]) -> Dict[str, Any]:
    return {
      'id': row[0],
      'user_id': row[1],
      'sender': row[2],
      'message': row[3],
    }

  def insert_row(self, user_id: int, sender: str, message: str, date: str) -> None:
    self.safe_insert_many_tuple([(None, user_id, sender, message, date)])

  def get_last_rows_from_user_id(self, user_id: int, count: int) -> List[Dict[str, Any]]:
    cursor = self._db.conn.cursor()
    cursor.execute('SELECT * FROM {} WHERE user_id=? ORDER BY id DESC LIMIT ?'.format(self._table_name), (user_id, count))
    return [self.tuple_to_dict(row) for row in cursor.fetchall()]



class Sqlite3TableConfig(Sqlite3Table):
  def _init_db(self) -> None:
    self._db.conn.execute(
      'CREATE TABLE IF NOT EXISTS {} (\
      key INTEGER PRIMARY KEY,\
      json_data TEXT\
      )'.format(self._table_name)
    )

  def tuple_to_dict(self, row: Tuple[Any, ...]) -> Dict[str, Any]:
    return {
      'key': row[0],
      'json_data': row[1],
    }
  
  def save_config(self, json_dict: dict) -> None:
    json_str = json.dumps(json_dict)

    key = 0
    # Update row if exists
    cursor = self._db.conn.cursor()
    cursor.execute('SELECT * FROM {} WHERE key=?'.format(self._table_name), (key,))
    if cursor.fetchone() is not None:
      cursor.execute('UPDATE {} SET json_data=? WHERE key=?'.format(self._table_name), (json_str, key))
    else:
      cursor.execute('INSERT INTO {} VALUES (?, ?)'.format(self._table_name), (key, json_str))
    self._db.conn.commit()
      
  def load_config(self) -> dict:
    key = 0
    cursor = self._db.conn.cursor()
    cursor.execute('SELECT * FROM {} WHERE key=?'.format(self._table_name), (key,))
    row = cursor.fetchone()
    if row is None:
      return {}
    json_str = row[1]

    return json.loads(json_str)



def build_history(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
  history = []
  for row in rows:
    if not row['message']:
      continue
    if row['sender'] == 'user':
      history.append({'role': 'user', 'content': row['message']})
    elif row['sender'] == 'assistant':
      history.append({'role': 'assistant', 'content': row['message']})
  return history



# Singletons
prompt_update_state = False
ai_answer_state = True
db = Sqlite3Db('chatbot.db')
room_info = Sqlite3TableRoomInfo(db, 'room_info')
room_chats = Sqlite3TableRoomChats(db, 'room_chats')
config = Sqlite3TableConfig(db, 'config')
