"""
This script creates the database and tables for
the vocabulary learning application.
"""
import sqlite3
from sqlite3 import IntegrityError, Connection
import pandas as pd
from typing import List, Tuple

class UserExistsError(Exception):
    pass

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

def insert_user(conn: Connection, user_name: str) -> None:
    """
    Insert a new user into the users table.

    Args:
        conn (Connection): SQLite database connection.
        user_name (str): Name of the user to insert.

    Raises:
        UserExistsError: If the user already exists in the database.
    """
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (user_name) VALUES (?)", (user_name,))
        conn.commit()
    except conn.IntegrityError:
        raise UserExistsError(f"User '{user_name}' already exists in the database.")
    finally:
        cur.close()

def remove_user(conn: Connection, user_id: int) -> None:
    """
    Remove user with user_id from users table
    and remove all associated rows in learning_data.

    Args:
        conn (Connection): SQLite database connection.
        user_id (int): ID of the user to remove.
    """
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE id=?", (user_id,))
        if cur.rowcount == 0:
            print(f"User with ID {user_id} does not exist.")
        else:
            cur.execute("DELETE FROM learning_data WHERE user_id=?", (user_id,))
            conn.commit()
            print(f"User with ID {user_id} removed successfully.")
    finally:
        cur.close()

def add_word_score(conn: Connection, user_id: int, word_id: int, score: int) -> None:
    """
    Add a row to learning_data for user with user_id
    for word_id and score. Score should be between 0 and 10.

    Args:
        conn (Connection): SQLite database connection.
        user_id (int): ID of the user.
        word_id (int): ID of the word.
        score (int): Score to add (between 0 and 10).
    """
    if not 0 <= score <= 10:
        raise ValueError("Score should be between 0 and 10.")
    
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO learning_data (user_id, word_id, score) VALUES (?, ?, ?)", (user_id, word_id, score))
        conn.commit()
        print("Word score added successfully.")
    except IntegrityError:
        # Check if user_id or word_id does not exist
        cur.execute("SELECT 1 FROM users WHERE id=?", (user_id,))
        if not cur.fetchone():
            print(f"User with ID {user_id} does not exist.")
        else:
            cur.execute("SELECT 1 FROM words WHERE id=?", (word_id,))
            if not cur.fetchone():
                print(f"Word with ID {word_id} does not exist.")
    finally:
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