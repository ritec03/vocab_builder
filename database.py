"""
This script creates the database and tables for
the vocabulary learning application.
"""
import sqlite3
from sqlite3 import IntegrityError, Connection
import pandas as pd
from typing import List, Tuple

MAX_USER_NAME_LENGTH = 20
MAX_SCORE = 10
MIN_SCORE = 0
DATABASE_PATH = "vocabulary_app.db"

class ValueDoesNotExistInDB(LookupError):
    """
    Error is thrown when a value queries in the database
    does not exist (eg. user_name or word_id)
    """
    pass

def connect_to_db(db_path: str) -> Connection:
    """
    Connect to database specified by path and enable
    foreign key checks.

    Args:
        db_path: str - path to database
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON") # add checks on foreign keys
    return conn

def create_db(conn: Connection) -> None:
    # Create a cursor object to execute SQL commands
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS words
        (
            id INTEGER PRIMARY KEY,
            word TEXT,
            pos TEXT,
            freq INTEGER,
            UNIQUE (word, pos)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users
        (
            id INTEGER PRIMARY KEY,
            user_name TEXT,
            UNIQUE (user_name)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS learning_data
        (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            word_id INTEGER,
            score INTERER CHECK (score >=0 AND score <= 10),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (word_id) REFERENCES words(id)
        )
    ''')

    # Commit the transaction (save changes)
    conn.commit()

    # Close the cursor and connection
    cur.close()

def add_words_to_db(conn: Connection, word_list: List[Tuple[str, str, int]]) -> None:
    """
    Insert tuples of (word, part-of-speech, frequency) into words table.
    If a combination of (word, pos) already exists in the database,
    only the freq count is updated.

    Args:
        conn (Connection): SQLite database connection.
        word_list (List[Tuple[str, str, int]]): list of tuples of (word, pos, freq),
            eg. [("Schule", "NOUN", 234), ...]
    """
    cur = conn.cursor()
    sql_insert = "INSERT INTO words (word, pos, freq) VALUES (?, ?, ?) ON CONFLICT(word, pos) DO UPDATE SET freq = excluded.freq"
    cur.executemany(sql_insert, word_list)
    conn.commit()
    cur.close()

def query_first_ten_entries(conn: Connection, table_name: str) -> None:
    """
    Print first ten entries of table with table_name if table exists.
    If table does not exist, print "table does not exist".

    Args:
        conn (Connection): SQLite database connection.
        table_name (str): Name of the table to query.
    """
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {table_name} LIMIT 10")
        rows = cur.fetchall()
        for row in rows:
            print(row)
    except sqlite3.OperationalError:
        print(f"Table '{table_name}' does not exist.")
    finally:
        cur.close()

def insert_user(conn: Connection, user_name: str) -> None:
    """
    Insert a new user into the users table.

    Args:
        conn (Connection): SQLite database connection.
        user_name (str): Username of the user to insert.

    Raises:
        ValueError: If the user already exists in the database.
        ValueError: If the user name is not a string or is longer than MAX_USER_NAME_LENGTH
    """
    if type(user_name) is not str or len(user_name) > MAX_USER_NAME_LENGTH:
        raise ValueError("Username is not a string or too long.")
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (user_name) VALUES (?)", (user_name,))
        conn.commit()
    except conn.IntegrityError:
        raise ValueError(f"User '{user_name}' already exists in the database.")
    finally:
        cur.close()

def remove_user(conn: Connection, user_id: int) -> None:
    """
    Remove user with user_id from users table
    and remove all associated rows in learning_data.

    Args:
        conn (Connection): SQLite database connection.
        user_id (int): ID of the user to remove.
    
    Raises:
        ValueDoesNotExistInDB if the user with user_id does not exist
    """
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE id=?", (user_id,))
        if cur.rowcount == 0:
            raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")
        else:
            cur.execute("DELETE FROM learning_data WHERE user_id=?", (user_id,))
            conn.commit()
            print(f"User with ID {user_id} removed successfully.")
    finally:
        cur.close()

def add_word_score(conn: Connection, user_id: int, word_id: int, score: int) -> None:
    """
    Add a row to learning_data for user with user_id
    for word_id and score. Score should be between MIN_SCORE and MAX_SCORE.

    Args:
        conn (Connection): SQLite database connection.
        user_id (int): ID of the user.
        word_id (int): ID of the word.
        score (int): Score to add (MIN_SCORE and MAX_SCORE).
    """
    if not MIN_SCORE <= score <= MAX_SCORE:
        raise ValueError(f"Score should be between {MIN_SCORE} and {MAX_SCORE}.")
    
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO learning_data (user_id, word_id, score) VALUES (?, ?, ?)", (user_id, word_id, score))
        conn.commit()
        print("Word score added successfully.")
    except IntegrityError:
        # Check if user_id or word_id does not exist
        cur.execute("SELECT 1 FROM users WHERE id=?", (user_id,))
        print(cur.fetchone())
        if not cur.fetchone():
            raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")
        else:
            cur.execute("SELECT 1 FROM words WHERE id=?", (word_id,))
            if not cur.fetchone():
                raise ValueDoesNotExistInDB(f"Word with ID {word_id} does not exist.")
    finally:
        cur.close()


db_conn = connect_to_db(DATABASE_PATH)
create_db(db_conn)

word_freq_output_file_path = "word_freq.txt"
word_freq_df_loaded = pd.read_csv(word_freq_output_file_path, sep="\t")
filtered_dataframe = word_freq_df_loaded[word_freq_df_loaded["count"] > 2]
list_of_tuples: List[Tuple[str, str, int]] = list(filtered_dataframe.to_records(index=False))
# convert numpy.int64 to Python integer
list_of_tuples = [(word, pos, int(freq)) for (word, pos, freq) in list_of_tuples]
add_words_to_db(db_conn, list_of_tuples)
db_conn.close()