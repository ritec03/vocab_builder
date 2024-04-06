import json
import unittest
import sqlite3
from data_structures import Score
from database import MAX_SCORE, MAX_USER_NAME_LENGTH, MIN_SCORE, DatabaseManager, SCHEMA_PATH, ValueDoesNotExistInDB
import os

from task import Evaluation, Task

# Define a test database file path
TEST_DB_FILE = "test_database.db"

class TestDatabaseFunctions(unittest.TestCase):
    def setUp(self):
        # Ensure the test database does not exist before starting each test
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        self.db_manager = DatabaseManager(TEST_DB_FILE)
        self.db_manager.create_db()

    def tearDown(self):
        # Close the database connection and delete the test database file
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def test_insert_user(self):
        # Test inserting a new user
        self.db_manager.insert_user("test_user")
        # Assert that the user is inserted successfully
        cur = self.db_manager.connection.cursor()
        cur.execute("SELECT user_name FROM users WHERE user_name=?", ("test_user",))
        result = cur.fetchone()
        self.assertIsNotNone(result)  # Check that a row is returned
        self.assertEqual(result[0], "test_user")  # Check that the inserted user name matches

    def test_insert_duplicate_user(self):
        # Test inserting a user with the same user name (should fail)
        self.db_manager.insert_user("test_user")
        with self.assertRaises(ValueError):
            self.db_manager.insert_user("test_user")  # Inserting the same user name should raise IntegrityError

    def test_remove_user_success(self):
        # Test removing an existing user
        self.db_manager.insert_user("test_user")
        self.db_manager.remove_user(1)  # Assuming the ID of the user just inserted is 1
        # Assert that the user is removed successfully
        cur = self.db_manager.connection.cursor()
        cur.execute("SELECT user_name FROM users WHERE id=?", (1,))
        result = cur.fetchone()
        self.assertIsNone(result)  # Check that no row is returned

    def test_remove_nonexistent_user(self):
        # Test removing a non-existent user
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.remove_user(1)  # Attempting to remove a non-existent user should raise an exception
            
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
        word_list = [("cat", "NOUN", 10), ("dog", "NOUN", 5)]
        self.db_manager.add_words_to_db(word_list)

        # Assert that the entries are added successfully
        cur = self.db_manager.connection.cursor()
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
        self.db_manager.add_words_to_db(word_list)  # Add initial entry
        word_list_update = [("cat", "NOUN", NEW_FREQ)]
        self.db_manager.add_words_to_db(word_list_update)  # Update frequency

        # Assert that the frequency is updated
        cur = self.db_manager.connection.cursor()
        cur.execute("SELECT freq FROM words WHERE word=? AND pos=?", ("cat", "NOUN"))
        freq = cur.fetchone()[0]
        self.assertEqual(freq, NEW_FREQ)  # Check that the frequency is updated to NEW_FREQ

    def test_add_existing_word_entry(self):
        # Test adding an existing word/pos entry to the words table
        word_list = [("cat", "NOUN", 10)]
        self.db_manager.add_words_to_db(word_list)  # Add initial entry
        self.db_manager.add_words_to_db(word_list)  # Attempt to add the same entry again

        # Assert that the entry remains the same (nothing happens)
        cur = self.db_manager.connection.cursor()
        cur.execute("SELECT freq FROM words WHERE word=? AND pos=?", ("cat", "NOUN"))
        freq = cur.fetchone()[0]
        self.assertEqual(freq, 10)  # Check that the frequency remains 10

    def test_add_word_score_update_existing(self):
        # Test adding a word score
        self.db_manager.insert_user("test_user")
        word_list = [("cat", "NOUN", 10)]
        self.db_manager.add_words_to_db(word_list)
        # Get the id of the word and the user
        cur = self.db_manager.connection.cursor()
        cur.execute("SELECT id FROM words WHERE word=? AND pos=?", ("cat", "NOUN"))
        word_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM users WHERE user_name=?", ("test_user",))
        user_id = cur.fetchone()[0]
        
        OLD_SCORE = 8
        NEW_SCORE = 5

        self.db_manager.add_word_score(user_id, word_id, OLD_SCORE)
        # Assert that the word score is added successfully
        cur.execute("SELECT score FROM learning_data WHERE user_id=? AND word_id=?", (user_id, word_id))
        score = cur.fetchone()[0]
        self.assertEqual(score, OLD_SCORE)  # Check that the score is OLD_SCORE
        # update the score again and see if it changes
        self.db_manager.add_word_score(user_id, word_id, NEW_SCORE)
        cur.execute("SELECT score FROM learning_data WHERE user_id=? AND word_id=?", (user_id, word_id))
        score = cur.fetchone()[0]
        self.assertEqual(score, NEW_SCORE)  # Check that the score is NEW_SCORE

    def test_add_word_score(self):
        # Test adding a word score
        self.db_manager.insert_user("test_user")
        word_list = [("cat", "NOUN", 10)]
        self.db_manager.add_words_to_db(word_list)
        # Get the id of the word and the user
        cur = self.db_manager.connection.cursor()
        cur.execute("SELECT id FROM words WHERE word=? AND pos=?", ("cat", "NOUN"))
        word_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM users WHERE user_name=?", ("test_user",))
        user_id = cur.fetchone()[0]
        self.db_manager.add_word_score(user_id, word_id, 8)

        # Assert that the word score is added successfully
        cur.execute("SELECT score FROM learning_data WHERE user_id=? AND word_id=?", (user_id, word_id))
        score = cur.fetchone()[0]
        self.assertEqual(score, 8)  # Check that the score is 8

    def test_add_word_score_nonexistent_user(self):
        word_list = [("cat", "NOUN", 10)]
        self.db_manager.add_words_to_db(word_list)
        # Get the id of the word
        cur = self.db_manager.connection.cursor()
        cur.execute("SELECT id FROM words WHERE word=? AND pos=?", ("cat", "NOUN"))
        word_id = cur.fetchone()[0]
        # Test adding a word score with a non-existent user
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.add_word_score(999, word_id, 8)  # Attempting to add a score for a non-existent user should raise an error

    def test_add_word_score_nonexistent_word_id(self):
        # Test adding a word score with a non-existent word_id
        self.db_manager.insert_user("test_user")
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.add_word_score(1, 999, 8)  # Attempting to add a score for a non-existent word_id should raise an error

    def test_add_word_score_incorrect_score(self):
        # Test adding a word score with an incorrect score
        self.db_manager.insert_user("test_user")
        word_list = [("cat", "NOUN", 10)]
        self.db_manager.add_words_to_db(word_list)
        with self.assertRaises(ValueError):
            self.db_manager.add_word_score(1, 1, (MIN_SCORE - 1))  # Attempting to add a negative score should raise an error
        with self.assertRaises(ValueError):
            self.db_manager.add_word_score(1, 1, (MAX_SCORE + 1))  # Attempting to add a score above the maximum should raise an error

class TestUpdateUserScores(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        self.db_manager = DatabaseManager(TEST_DB_FILE)
        self.db_manager.create_db()
        # Insert a test user and words to ensure they exist
        self.db_manager.insert_user("test_user")
        self.db_manager.add_words_to_db([("word1", "noun", 1), ("word2", "verb", 2), ("word3", "adj", 3)])
        self.user_id = self.db_manager.connection.execute("SELECT id FROM users WHERE user_name='test_user'").fetchone()[0]
        self.word_ids = [self.db_manager.connection.execute("SELECT id FROM words WHERE word=?", (f"word{i}",)).fetchone()[0] for i in range(1, 4)]

    def tearDown(self):
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def test_update_user_scores_single_score_update(self):
        # Test adding a single score and updating it
        initial_scores = [Score(word_id=self.word_ids[0], score=5)]
        updated_scores = [Score(word_id=self.word_ids[0], score=7)]
        self.db_manager.update_user_scores(self.user_id, initial_scores)
        self.db_manager.update_user_scores(self.user_id, updated_scores)
        scores = self.db_manager.retrieve_user_scores(self.user_id)
        self.assertEqual(scores[0].score, 7)

    def test_update_user_scores_multiple_scores_update(self):
        # Test adding three scores, then updating two of them
        initial_scores = [Score(word_id=self.word_ids[i], score=3 + i) for i in range(3)]
        updated_scores = [Score(word_id=self.word_ids[0], score=8), Score(word_id=self.word_ids[1], score=9)]
        self.db_manager.update_user_scores(self.user_id, initial_scores)
        self.db_manager.update_user_scores(self.user_id, updated_scores)
        scores = self.db_manager.retrieve_user_scores(self.user_id)
        self.assertEqual(scores[0].score, 8)
        self.assertEqual(scores[1].score, 9)
        self.assertEqual(scores[2].score, 5)  # Unchanged

    def test_update_user_scores_nonexistent_word(self):
        # Test updating with a word_id that does not exist
        scores = [Score(word_id=9999, score=7)]  # Assuming 9999 is an ID that does not exist
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.update_user_scores(self.user_id, scores)

    def test_update_user_scores_nonexistent_user(self):
        # Test updating a score for a non-existent user
        scores = [Score(word_id=self.word_ids[0], score=7)]
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.update_user_scores(9999, scores)  # Assuming 9999 is a non-existent user ID

class TestRetrieveUserScores(unittest.TestCase):
    def tearDown(self):
        """
        Class method to clean up the environment after all tests.
        """
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def setUp(self):
        """
        Method to set up the environment before each test.
        """
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        self.db_manager = DatabaseManager(TEST_DB_FILE)
        self.db_manager.create_db()
        # Insert test data
        self.db_manager.insert_user("test_user")
        # Insert two words into the database
        self.db_manager.add_words_to_db([("test", "noun", 1), ("study", "verb", 2)])
        user_id, word_ids = self.get_test_user_and_word_ids()
        # Add scores for both words for the user
        self.db_manager.add_word_score(user_id, word_ids[0], 5)
        self.db_manager.add_word_score(user_id, word_ids[1], 8)

    def get_test_user_and_word_ids(self):
        """
        Helper method to retrieve test user and word IDs.
        This method now returns a list of word IDs to handle multiple words.
        """
        user_id = self.db_manager.connection.execute("SELECT id FROM users WHERE user_name=?", ("test_user",)).fetchone()[0]
        word_ids = [
            self.db_manager.connection.execute("SELECT id FROM words WHERE word=?", ("test",)).fetchone()[0],
            self.db_manager.connection.execute("SELECT id FROM words WHERE word=?", ("study",)).fetchone()[0]
        ]
        return user_id, word_ids

    def test_user_with_scores(self):
        """
        Test retrieving scores for a user with existing scores for multiple words.
        """
        user_id, word_ids = self.get_test_user_and_word_ids()
        scores = self.db_manager.retrieve_user_scores(user_id)
        self.assertIsInstance(scores, list)
        self.assertEqual(len(scores), 2)  # Expecting scores for 2 words
        # Ensure that the scores list contains Score objects with the correct scores
        scores_dict = {score.word_id: score.score for score in scores}
        self.assertEqual(scores_dict.get(word_ids[0]), 5)
        self.assertEqual(scores_dict.get(word_ids[1]), 8)

    def test_user_without_scores(self):
        """
        Test retrieving scores for a user without scores.
        """
        self.db_manager.insert_user("another_user")
        another_user_id = self.db_manager.connection.execute("SELECT id FROM users WHERE user_name=?", ("another_user",)).fetchone()[0]
        scores = self.db_manager.retrieve_user_scores(another_user_id)
        self.assertIsInstance(scores, list)
        self.assertEqual(len(scores), 0)

    def test_nonexistent_user(self):
        """
        Test retrieving scores for a nonexistent user.
        """
        with self.assertRaises(ValueDoesNotExistInDB):
            scores = self.db_manager.retrieve_user_scores(9999)  # Assuming 9999 is an ID that does not exist

class TestSaveUserLessonData(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        self.db_manager = DatabaseManager(TEST_DB_FILE)
        self.db_manager.create_db()
        self.db_manager.insert_user("test_user")
        self.user_id = self.db_manager.connection.execute("SELECT id FROM users WHERE user_name=?", ("test_user",)).fetchone()[0]

    def tearDown(self):
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def test_add_non_list_evaluation_object(self):
        """
        Test try to add an object that is not a list of evaluation objects.
        """
        with self.assertRaises(TypeError):
            self.db_manager.save_user_lesson_data(self.user_id, "This is not a list of Evaluation objects")

    def test_nonexistent_user(self):
        """
        Test try to save lesson data for a non-existent user.
        """
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.save_user_lesson_data(9999, [])

    def test_add_empty_evaluation_object(self):
        """
        Test tries to add an empty evaluation object (which history entry is an empty list).
        """
        with self.assertRaises(ValueError):
            self.db_manager.save_user_lesson_data(self.user_id, [Evaluation()])  # Passing an Evaluation object with an empty history

    def test_add_two_evaluations_with_two_history_entries_each(self):
        """
        Test with a list that contains two evaluations, each of which contains two history entries.
        """
        task = Task(template_name="Test Template", resources=["test", "study"], learning_items=set())
        evaluation1 = Evaluation()
        evaluation1.add_entry(task, "Response 1", [Score(word_id=1, score=5)], None)
        evaluation1.add_entry(task, "Response 2", [Score(word_id=2, score=8)], None)
        
        evaluation2 = Evaluation()
        evaluation2.add_entry(task, "Response 3", [Score(word_id=1, score=6)], None)
        evaluation2.add_entry(task, "Response 4", [Score(word_id=2, score=7)], None)
        
        self.db_manager.save_user_lesson_data(self.user_id, [evaluation1, evaluation2])
        
        # Fetch saved lesson data to validate
        cur = self.db_manager.connection.cursor()
        cur.execute("SELECT evaluation_json FROM user_lesson_history WHERE user_id=?", (self.user_id,))
        saved_data = cur.fetchone()[0]
        cur.close()
        
        saved_evaluations = json.loads(saved_data)
        self.assertEqual(len(saved_evaluations), 2)  # Ensure there are two evaluations saved
        self.assertEqual(len(saved_evaluations[0]['history']), 2)  # First evaluation has two history entries
        self.assertEqual(len(saved_evaluations[1]['history']), 2)  # Second evaluation has two history entries


if __name__ == '__main__':
    unittest.main()
