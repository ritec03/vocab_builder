import json
import unittest
import sqlite3

from sqlalchemy import select
from data_structures import Language, LexicalItem, Resource, Score, TaskType
from database import MAX_SCORE, MAX_USER_NAME_LENGTH, MIN_SCORE, SCHEMA_PATH, ValueDoesNotExistInDB
from database_orm import DatabaseManager, LearningDataDBObj, WordDBObj
import os

from task import OneWayTranslaitonTask, Task
from evaluation import Evaluation, HistoryEntry
from task_template import TaskTemplate

# Define a test database file path
TEST_DB_FILE = "test_database.db"

class TestDatabaseFunctions(unittest.TestCase):
    def setUp(self):
        # Ensure the test database does not exist before starting each test
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        self.db_manager = DatabaseManager(TEST_DB_FILE)

    def tearDown(self):
        # Close the database connection and delete the test database file
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def test_insert_user(self):
        # Test inserting a new user
        user_id = self.db_manager.insert_user("test_user")
        # Assert that the user is inserted successfully
        user = self.db_manager.get_user_by_id(user_id)
        self.assertIsNotNone(user)  # Check that a row is returned
        self.assertEqual(user.user_name, "test_user")  # Check that the inserted user name matches

    def test_insert_duplicate_user(self):
        # Test inserting a user with the same user name (should fail)
        self.db_manager.insert_user("test_user")
        with self.assertRaises(ValueError):
            self.db_manager.insert_user("test_user")  # Inserting the same user name should raise IntegrityError

    def test_remove_user_success(self):
        # Test removing an existing user
        user_id = self.db_manager.insert_user("test_user")
        self.db_manager.remove_user(user_id)
        # Assert that the user is removed successfully
        user = self.db_manager.get_user_by_id(user_id)
        self.assertIsNone(user)  # Check that no row is returned

    def test_remove_nonexistent_user(self):
        # Test removing a non-existent user
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.remove_user(999)  # Attempting to remove a non-existent user should raise an exception
            
    def test_add_user_invalid_name_type(self):
        # Test adding a user with a user name that is not a string
        with self.assertRaises(ValueError):
            self.db_manager.insert_user(123)  # Inserting a non-string user name should raise a ValueError

    def test_add_user_long_name(self):
        # Test adding a user with a user name that is too long
        long_username = "a" * (MAX_USER_NAME_LENGTH + 1)  # Create a user name longer than MAX_USER_NAME_LENGTH
        with self.assertRaises(ValueError):
            self.db_manager.insert_user(long_username)  # Inserting a long user name should raise a ValueError

    def test_add_two_word_entries(self):
        # Test adding two word entries to the words table successfully
        test_words = {"cat": ("cat", "NOUN", 10), "dog": ("dog", "NOUN", 5)}
        word_ids = self.db_manager.add_words_to_db(list(test_words.values()))

        # Assert that the entries are added successfully

        for id in word_ids:
            word = self.db_manager.get_word_by_id(id)
            test_word = test_words[word.item]
            self.assertEqual(word.item, test_word[0])
            self.assertEqual(word.pos, test_word[1])
            self.assertEqual(word.freq, test_word[2])

        self.assertEqual(len(word_ids), len(list(test_words.values())))  # Check that there are no entires left

    def test_update_existing_word_entry(self):
        # Test updating an existing word/pos entry in the words table
        OLD_FREQ = 10
        NEW_FREQ = 15
        word_list = [("cat", "NOUN", OLD_FREQ)]
        self.db_manager.add_words_to_db(word_list)  # Add initial entry
        word_list_update = [("cat", "NOUN", NEW_FREQ)]
        word_ids = self.db_manager.add_words_to_db(word_list_update)  # Update frequency

        # Assert that the frequency is updated
        word = self.db_manager.get_word_by_id(word_ids[0])
        self.assertEqual(word.freq, NEW_FREQ)  # Check that the frequency is updated to NEW_FREQ

    def test_add_existing_word_entry(self):
        # Test adding an existing word/pos entry to the words table
        word_list = [("cat", "NOUN", 10)]
        self.db_manager.add_words_to_db(word_list)  # Add initial entry
        word_list_duplicate = [("cat", "NOUN", 10)]
        word_ids = self.db_manager.add_words_to_db(word_list_duplicate)  # Attempt to add the same entry again

        # Assert that only one word exists and its frequency remains the same
        word = self.db_manager.get_word_by_id(word_ids[0])
        self.assertEqual(word.freq, 10)  # Check that the frequency remains 10
        # Assert that no new rows are added
        all_words = self.db_manager.session.execute(select(WordDBObj)).all() # TODO remove sqlalchemy code
        self.assertEqual(len(all_words), 1)  # Ensure only one word entry exists

    def test_add_word_score_update_existing(self):
        # Test adding a word score
        user_id = self.db_manager.insert_user("test_user")
        word_list = [("cat", "NOUN", 10)]
        word_ids = self.db_manager.add_words_to_db(word_list)

        word_id = word_ids[0]
        OLD_SCORE = 8
        NEW_SCORE = 5

        # Add old score
        self.db_manager.add_word_score(user_id, Score(word_id, OLD_SCORE))
        # Assert that the word score is added successfully
        score = self.db_manager.get_score(user_id, word_id)
        self.assertEqual(score, OLD_SCORE)  # Check that the score is OLD_SCORE

        # Update the score
        self.db_manager.add_word_score(user_id, Score(word_id, NEW_SCORE))
        # Assert that the score is updated
        updated_score = self.db_manager.get_score(user_id, word_id)
        self.assertEqual(updated_score, NEW_SCORE)  # Check that the score is NEW_SCORE

    def test_add_word_score(self):
        user_id = self.db_manager.insert_user("test_user")
        word_list = [("cat", "NOUN", 10)]
        word_ids = self.db_manager.add_words_to_db(word_list)
        word_id = word_ids[0]
        score_value = 8
        self.db_manager.add_word_score(user_id, Score(word_id, score_value))

        # Assert that the word score is added successfully
        entry = self.db_manager.session.execute(
            select(LearningDataDBObj).where(
                LearningDataDBObj.user_id == user_id,
                LearningDataDBObj.word_id == word_id
            )
        ).scalar()
        self.assertEqual(entry.score, score_value)  # Check that the score is 8

    def test_add_word_score_nonexistent_user(self):
        word_list = [("cat", "NOUN", 10)]
        word_ids = self.db_manager.add_words_to_db(word_list)
        word_id = word_ids[0]
        score_value = 8

        # Test adding a word score with a non-existent user
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.add_word_score(999, Score(word_id, score_value))  # Attempting to add a score for a non-existent user should raise an error

    def test_add_word_score_nonexistent_word_id(self):
        user_id = self.db_manager.insert_user("test_user")
        score_value = 8

        # Test adding a word score with a non-existent word_id
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.add_word_score(user_id, Score(999, score_value))  # Attempting to add a score for a non-existent word should raise an error

    def test_add_word_score_incorrect_score(self):
        user_id = self.db_manager.insert_user("test_user")
        word_list = [("cat", "NOUN", 10)]
        word_ids = self.db_manager.add_words_to_db(word_list)
        word_id = word_ids[0]

        # Test adding a word score with an incorrect score
        with self.assertRaises(ValueError):
            self.db_manager.add_word_score(user_id, Score(word_id, MIN_SCORE - 1))  # Attempting to add a negative score should raise an error
        with self.assertRaises(ValueError):
            self.db_manager.add_word_score(user_id, Score(word_id, MAX_SCORE + 1))  # Attempting to add a score above the maximum should raise an error
