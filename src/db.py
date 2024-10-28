import re
import sqlite3
import os
import time
import random
from typing import List, Dict, Any, Generator, Tuple

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