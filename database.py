"""
This script creates the database and tables for
the vocabulary learning application.
"""
import json
import sqlite3
from sqlite3 import IntegrityError, Connection
import pandas as pd
from typing import List, Tuple
from data_structures import MAX_SCORE, MAX_USER_NAME_LENGTH, MIN_SCORE, Score
from task import Evaluation, Task

DATABASE_PATH = "vocabulary_app.db"
SCHEMA_PATH = "schema.sql"


class ValueDoesNotExistInDB(LookupError):
    """
    Error is thrown when a value queries in the database
    does not exist (eg. user_name or word_id)
    """
    pass

class DatabaseManager:
    def __init__(self, db_path: str):
        """
        Initialize the database manager and establish a connection to the database.
        """
        self.connection = self.connect_to_db(db_path)

    def connect_to_db(self, db_path: str) -> Connection:
        """
        Connect to database specified by path and enable
        foreign key checks.

        Args:
            db_path: str - path to database
        """
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON") # add checks on foreign keys
        return conn

    def create_db(self) -> None:
        # Create a cursor object to execute SQL commands
        cur = self.connection.cursor()

        # Read the SQL file
        with open(SCHEMA_PATH, 'r') as file:
            sql_script = file.read()

        # Execute the SQL script
        cur.executescript(sql_script)

        # Commit the transaction (save changes)
        self.connection.commit()

        # Close the cursor and connection
        cur.close()

    def add_words_to_db(self, word_list: List[Tuple[str, str, int]]) -> None:
        """
        Insert tuples of (word, part-of-speech, frequency) into words table.
        If a combination of (word, pos) already exists in the database,
        only the freq count is updated.

        Args:
            word_list (List[Tuple[str, str, int]]): list of tuples of (word, pos, freq),
                eg. [("Schule", "NOUN", 234), ...]
        """
        cur = self.connection.cursor()
        sql_insert = "INSERT INTO words (word, pos, freq) VALUES (?, ?, ?) ON CONFLICT(word, pos) DO UPDATE SET freq = excluded.freq"
        cur.executemany(sql_insert, word_list)
        self.connection.commit()
        cur.close()

    def query_first_ten_entries(self, table_name: str) -> None:
        """
        Print first ten entries of table with table_name if table exists.
        If table does not exist, print "table does not exist".

        Args:
            table_name (str): Name of the table to query.
        """
        cur = self.connection.cursor()
        try:
            cur.execute(f"SELECT * FROM {table_name} LIMIT 10")
            rows = cur.fetchall()
            for row in rows:
                print(row)
        except sqlite3.OperationalError:
            print(f"Table '{table_name}' does not exist.")
        finally:
            cur.close()

    def insert_user(self, user_name: str) -> None:
        """
        Insert a new user into the users table.

        Args:
            user_name (str): Username of the user to insert.

        Raises:
            ValueError: If the user already exists in the database.
            ValueError: If the user name is not a string or is longer than MAX_USER_NAME_LENGTH
        """
        if type(user_name) is not str or len(user_name) > MAX_USER_NAME_LENGTH:
            raise ValueError("Username is not a string or too long.")
        cur = self.connection.cursor()
        try:
            cur.execute("INSERT INTO users (user_name) VALUES (?)", (user_name,))
            self.connection.commit()
        except self.connection.IntegrityError:
            raise ValueError(f"User '{user_name}' already exists in the database.")
        finally:
            cur.close()

    def remove_user(self, user_id: int) -> None:
        """
        Remove user with user_id from users table
        and remove all associated rows in learning_data.

        Args:
            user_id (int): ID of the user to remove.
        
        Raises:
            ValueDoesNotExistInDB if the user with user_id does not exist
        """
        cur = self.connection.cursor()
        try:
            cur.execute("DELETE FROM users WHERE id=?", (user_id,))
            if cur.rowcount == 0:
                raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")
            else:
                cur.execute("DELETE FROM learning_data WHERE user_id=?", (user_id,))
                self.connection.commit()
                print(f"User with ID {user_id} removed successfully.")
        finally:
            cur.close()

    def add_word_score(self, user_id: int, word_id: int, score: int) -> None:
        """
        Adds or updates a row in learning_data for the user with user_id
        for word_id with the given score. Score should be between MIN_SCORE and MAX_SCORE.
        If a score for the word already exists for the user, it is updated.

        Args:
            user_id (int): ID of the user.
            word_id (int): ID of the word.
            score (int): Score to add (MIN_SCORE and MAX_SCORE).
        """
        if not MIN_SCORE <= score <= MAX_SCORE:
            raise ValueError(f"Score should be between {MIN_SCORE} and {MAX_SCORE}.")

        cur = self.connection.cursor()
        # Check for existing user and word entries
        cur.execute("SELECT 1 FROM users WHERE id=?", (user_id,))
        if not cur.fetchone():
            cur.close()
            raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")

        cur.execute("SELECT 1 FROM words WHERE id=?", (word_id,))
        if not cur.fetchone():
            cur.close()
            raise ValueDoesNotExistInDB(f"Word with ID {word_id} does not exist.")

        # Insert or update the score
        try:
            cur.execute("""
                INSERT INTO learning_data (user_id, word_id, score)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, word_id)
                DO UPDATE SET score = excluded.score
            """, (user_id, word_id, score))
            self.connection.commit()
            print("Word score added or updated successfully.")
        except IntegrityError as e:
            # Handle any integrity errors
            raise Exception(f"Integrity error occurred: {e}")
        finally:
            cur.close()

    def update_user_scores(self, user_id: int, lesson_scores: List[Score]) -> None:
        """
        Update user scores for the lesson scores which is a list of scores
        for each word_id. If the word with a score for the user is already in db,
        udpate it, add it otherwise.
        If non existent user - raise ValueDoesNotExistInDB
        If ther eis a word or words that are not in db - raise ValueDoesNotExistInDB
        """
        cur = self.connection.cursor()
        # Verify the user exists
        cur.execute("SELECT id FROM users WHERE id=?", (user_id,))
        if cur.fetchone() is None:
            raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")

        for score in lesson_scores:
            # Verify each word exists
            cur.execute("SELECT id FROM words WHERE id=?", (score.word_id,))
            if cur.fetchone() is None:
                raise ValueDoesNotExistInDB(f"Word with ID {score.word_id} does not exist.")

            # Update or insert the score
            cur.execute("""
                INSERT INTO learning_data (user_id, word_id, score)
                VALUES (?, ?, ?) ON CONFLICT(user_id, word_id)
                DO UPDATE SET score=excluded.score
            """, (user_id, score.word_id, score.score))
        self.connection.commit()

    def retrieve_user_scores(self, user_id: int) -> List[Score]:
        """
        Retrieves word score data of a user from the learning_data table
        and returnes them as a list of Score.
        Raise ValueDoesNotExistInDB error if non-existent user is requested.
        """
        cur = self.connection.cursor()
        # Verify the user exists
        cur.execute("SELECT id FROM users WHERE id=?", (user_id,))
        if cur.fetchone() is None:
            raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")

        cur.execute("SELECT word_id, score FROM learning_data WHERE user_id=?", (user_id,))
        scores = [Score(word_id=row[0], score=row[1]) for row in cur.fetchall()]
        return scores

    def save_user_lesson_data(self, user_id: int, lesson_data: List[Evaluation]) -> None:
        """
        Saves lesson data as a json string of lesson data in user lesson history table.

        test - try to add an object that is not an evaluation object
        test - non existent user
        test - tries to add an empty evaluation object (which history entry is empty list)
        test - test with a list that contains two evaluations, each of which contains two
            history entries.

        raises TypeError if lesson_data is not the right object
        raises ValueDoesNotExistInDB if user does not exist
        raises ValueError if there is an empty list, or it has only one evaluation without
        history entries
        """
        if not isinstance(lesson_data, list) or not all(isinstance(evaluation, Evaluation) for evaluation in lesson_data):
            raise TypeError("lesson_data must be a list of Evaluation objects")
        
        # Verify the user exists
        cur = self.connection.cursor()
        cur.execute("SELECT id FROM users WHERE id=?", (user_id,))
        if cur.fetchone() is None:
            raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")

        # Serialize and save lesson data
        if (len(lesson_data) == 0) or (len(lesson_data) == 1 and len(lesson_data[0].get_history()) == 0):
            raise ValueError("Lesson data contains no evaluation or only one evaluation with no history entries.")
        serialized_data = json.dumps([evaluation.to_json() for evaluation in lesson_data])
        cur.execute("INSERT INTO user_lesson_history (user_id, evaluation_json) VALUES (?, ?)", (user_id, serialized_data))
        self.connection.commit()


    def fetch_tasks(self, criteria: List) -> List[Task]:
        query = self.compose_query_from_criteria(criteria)
        # Execute the query against the database
        raise NotImplementedError()

    def compose_query_from_criteria(self, criteria: List) -> str:
        # This method should translate the criteria objects into a database query.
        raise NotImplementedError()
    
    def close(self):
        """
        Closes the database connection.
        """
        if self.connection:
            self.connection.close()

db = DatabaseManager(DATABASE_PATH)
db.create_db()

word_freq_output_file_path = "word_freq.txt"
word_freq_df_loaded = pd.read_csv(word_freq_output_file_path, sep="\t")
filtered_dataframe = word_freq_df_loaded[word_freq_df_loaded["count"] > 2]
list_of_tuples: List[Tuple[str, str, int]] = list(filtered_dataframe.to_records(index=False))
# convert numpy.int64 to Python integer
list_of_tuples = [(word, pos, int(freq)) for (word, pos, freq) in list_of_tuples]
db.add_words_to_db(list_of_tuples)
db.close()