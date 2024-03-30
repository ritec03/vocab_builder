"""
This script creates the database and tables for
the vocabulary learning application.
"""
import sqlite3
import pandas as pd
from typing import List, Tuple

# Define type hints for SQLite connection and cursor
Connection = sqlite3.Connection
Cursor = sqlite3.Cursor

def connect_to_db() -> Connection:
    conn = sqlite3.connect('vocabulary_app.db')
    return conn

def create_db(conn: Connection) -> None:

    # Create a cursor object to execute SQL commands
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS words
        (id INTEGER PRIMARY KEY, word TEXT, pos TEXT, freq INTEGER)
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users
        (id INTEGER PRIMARY KEY, user_name TEXT)
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS learning_data
        (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            word_id INTEGER,
            score INTERER CHECK (score >=0 AND score <= 10),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Commit the transaction (save changes)
    conn.commit()

    # Close the cursor and connection
    cur.close()

def add_words_to_db(conn:Connection, word_list: List[Tuple[str, str, int]]) -> None:
    cur = conn.cursor()
    sql_insert = "INSERT INTO words (word, pos, freq) VALUES (?, ?, ?)"
    cur.executemany(sql_insert, word_list)
    conn.commit()
    cur.close()

def query_first_ten_entries(conn: Connection) -> None:
    cur = conn.cursor()
    cur.execute("SELECT * FROM words LIMIT 10")
    rows = cur.fetchall()
    for row in rows:
        print(row)
    cur.close()

db_conn = connect_to_db()
create_db(db_conn)

word_freq_output_file_path = "word_freq.txt"
word_freq_df_loaded = pd.read_csv(word_freq_output_file_path, sep="\t")
filtered_dataframe = word_freq_df_loaded[word_freq_df_loaded["count"] > 2]
list_of_tuples: List[Tuple[str, str, int]] = list(filtered_dataframe.to_records(index=False))
# convert numpy.int64 to Python integer
list_of_tuples = [(word, pos, int(freq)) for (word, pos, freq) in list_of_tuples]
add_words_to_db(db_conn, list_of_tuples)
query_first_ten_entries(db_conn)
db_conn.close()