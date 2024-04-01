import unittest
import sqlite3
from database import create_db, insert_user, remove_user, add_word_score, add_words_to_db, ValueDoesNotExistInDB, MIN_SCORE, MAX_SCORE, MAX_USER_NAME_LENGTH, connect_to_db
import os

# Define a test database file path
TEST_DB_FILE = "test_database.db"

class TestDatabaseFunctions(unittest.TestCase):
    def setUp(self):
        # Connect to the test database and create tables
        self.conn = connect_to_db(TEST_DB_FILE)
        create_db(self.conn)

    def tearDown(self):
        # Close the database connection and delete the test database file
        self.conn.close()
        os.remove(TEST_DB_FILE)

    def test_insert_user(self):
        # Test inserting a new user
        insert_user(self.conn, "test_user")
        # Assert that the user is inserted successfully
        cur = self.conn.cursor()
        cur.execute("SELECT user_name FROM users WHERE user_name=?", ("test_user",))
        result = cur.fetchone()
        self.assertIsNotNone(result)  # Check that a row is returned
        self.assertEqual(result[0], "test_user")  # Check that the inserted user name matches

    def test_insert_duplicate_user(self):
        # Test inserting a user with the same user name (should fail)
        insert_user(self.conn, "test_user")
        with self.assertRaises(ValueError):
            insert_user(self.conn, "test_user")  # Inserting the same user name should raise IntegrityError

    def test_remove_user_success(self):
        # Test removing an existing user
        insert_user(self.conn, "test_user")
        remove_user(self.conn, 1)  # Assuming the ID of the user just inserted is 1
        # Assert that the user is removed successfully
        cur = self.conn.cursor()
        cur.execute("SELECT user_name FROM users WHERE id=?", (1,))
        result = cur.fetchone()
        self.assertIsNone(result)  # Check that no row is returned

    def test_remove_nonexistent_user(self):
        # Test removing a non-existent user
        with self.assertRaises(ValueDoesNotExistInDB):
            remove_user(self.conn, 1)  # Attempting to remove a non-existent user should raise an exception
            
    def test_add_user_invalid_name_type(self):
        # Test adding a user with a user name that is not a string
        with self.assertRaises(ValueError):
            insert_user(self.conn, 123)  # Inserting a non-string user name should raise a ValueError

    def test_add_user_long_name(self):
        # Test adding a user with a user name that is too long
        long_username = "a" * (MAX_USER_NAME_LENGTH + 1)  # Create a user name longer than MAX_USER_NAME_LENGTH
        with self.assertRaises(ValueError):
            insert_user(self.conn, long_username)  # Inserting a long user name should raise a ValueError

    def test_add_two_word_entries(self):
        # Test adding two word entries to the words table successfully
        word_list = [("cat", "NOUN", 10), ("dog", "NOUN", 5)]
        add_words_to_db(self.conn, word_list)

        # Assert that the entries are added successfully
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM words")
        count = cur.fetchone()[0]
        self.assertEqual(count, 2)  # Check that there are two entries in the words table
        # Check that entries have the correct values
        cur.execute("SELECT * FROM words")
        rows = cur.fetchall()
        self.assertEqual(rows[0][1], "cat")  # Check the first word
        self.assertEqual(rows[1][1], "dog")  # Check the second word

    def test_update_existing_word_entry(self):
        # Test updating an existing word/pos entry in the words table
        OLD_FREQ = 10
        NEW_FREQ = 15
        word_list = [("cat", "NOUN", OLD_FREQ)]
        add_words_to_db(self.conn, word_list)  # Add initial entry
        word_list_update = [("cat", "NOUN", NEW_FREQ)]
        add_words_to_db(self.conn, word_list_update)  # Update frequency

        # Assert that the frequency is updated
        cur = self.conn.cursor()
        cur.execute("SELECT freq FROM words WHERE word=? AND pos=?", ("cat", "NOUN"))
        freq = cur.fetchone()[0]
        self.assertEqual(freq, NEW_FREQ)  # Check that the frequency is updated to NEW_FREQ

    def test_add_existing_word_entry(self):
        # Test adding an existing word/pos entry to the words table
        word_list = [("cat", "NOUN", 10)]
        add_words_to_db(self.conn, word_list)  # Add initial entry
        add_words_to_db(self.conn, word_list)  # Attempt to add the same entry again

        # Assert that the entry remains the same (nothing happens)
        cur = self.conn.cursor()
        cur.execute("SELECT freq FROM words WHERE word=? AND pos=?", ("cat", "NOUN"))
        freq = cur.fetchone()[0]
        self.assertEqual(freq, 10)  # Check that the frequency remains 10

    def test_add_word_score(self):
        # Test adding a word score
        insert_user(self.conn, "test_user")
        word_list = [("cat", "NOUN", 10)]
        add_words_to_db(self.conn, word_list)
        # Get the id of the word and the user
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM words WHERE word=? AND pos=?", ("cat", "NOUN"))
        word_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM users WHERE user_name=?", ("test_user",))
        user_id = cur.fetchone()[0]
        add_word_score(self.conn, user_id, word_id, 8)  # Assuming user_id and word_id are both 1

        # Assert that the word score is added successfully
        cur.execute("SELECT score FROM learning_data WHERE user_id=? AND word_id=?", (user_id, word_id))
        score = cur.fetchone()[0]
        self.assertEqual(score, 8)  # Check that the score is 8

    def test_add_word_score_nonexistent_user(self):
        word_list = [("cat", "NOUN", 10)]
        add_words_to_db(self.conn, word_list)
        # Get the id of the word
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM words WHERE word=? AND pos=?", ("cat", "NOUN"))
        word_id = cur.fetchone()[0]
        # Test adding a word score with a non-existent user
        with self.assertRaises(ValueDoesNotExistInDB):
            add_word_score(self.conn, 999, word_id, 8)  # Attempting to add a score for a non-existent user should raise an error

    def test_add_word_score_nonexistent_word_id(self):
        # Test adding a word score with a non-existent word_id
        insert_user(self.conn, "test_user")
        with self.assertRaises(ValueDoesNotExistInDB):
            add_word_score(self.conn, 1, 999, 8)  # Attempting to add a score for a non-existent word_id should raise an error

    def test_add_word_score_incorrect_score(self):
        # Test adding a word score with an incorrect score
        insert_user(self.conn, "test_user")
        word_list = [("cat", "NOUN", 10)]
        add_words_to_db(self.conn, word_list)
        with self.assertRaises(ValueError):
            add_word_score(self.conn, 1, 1, (MIN_SCORE - 1))  # Attempting to add a negative score should raise an error
        with self.assertRaises(ValueError):
            add_word_score(self.conn, 1, 1, (MAX_SCORE + 1))  # Attempting to add a score above the maximum should raise an error

if __name__ == '__main__':
    unittest.main()
