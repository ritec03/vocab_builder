import unittest
import sqlite3
from database import create_db, insert_user, remove_user, add_word_score, query_first_ten_entries, UserExistsError
import os

# Define a test database file path
TEST_DB_FILE = "test_database.db"

class TestDatabaseFunctions(unittest.TestCase):
    def setUp(self):
        # Connect to the test database and create tables
        self.conn = sqlite3.connect(TEST_DB_FILE)
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
        with self.assertRaises(UserExistsError):
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
        with self.assertRaises(sqlite3.Error):
            remove_user(self.conn, 1)  # Attempting to remove a non-existent user should raise an exception


    # add a word score 
            
    # add a word score with non-existent user
            
    # add a word score with non-existent word_id
            
    # add aword score with an incorrect score (MIN_SCORE-1, MAX_SCORE + 1)


if __name__ == '__main__':
    unittest.main()
