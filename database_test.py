import json
import unittest
import sqlite3
from data_structures import Language, LexicalItem, Resource, Score, TaskType
from database import MAX_SCORE, MAX_USER_NAME_LENGTH, MIN_SCORE, DatabaseManager, SCHEMA_PATH, ValueDoesNotExistInDB
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

        score_old = Score(word_id, OLD_SCORE)
        self.db_manager.add_word_score(user_id, score_old)
        # Assert that the word score is added successfully
        cur.execute("SELECT score FROM learning_data WHERE user_id=? AND word_id=?", (user_id, word_id))
        score = cur.fetchone()[0]
        self.assertEqual(score, OLD_SCORE)  # Check that the score is OLD_SCORE
        # update the score again and see if it changes
        score_new = Score(word_id, NEW_SCORE)
        self.db_manager.add_word_score(user_id, score_new)
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
        score_obj = Score(word_id, 8)
        self.db_manager.add_word_score(user_id, score_obj)

        # Assert that the word score is added successfully
        cur.execute("SELECT score FROM learning_data WHERE user_id=? AND word_id=?", (user_id, word_id))
        score = cur.fetchone()[0]
        self.assertEqual(score, score_obj.score)  # Check that the score is 8

    def test_add_word_score_nonexistent_user(self):
        word_list = [("cat", "NOUN", 10)]
        self.db_manager.add_words_to_db(word_list)
        # Get the id of the word
        cur = self.db_manager.connection.cursor()
        cur.execute("SELECT id FROM words WHERE word=? AND pos=?", ("cat", "NOUN"))
        word_id = cur.fetchone()[0]
        score_obj = Score(word_id, 8)
        # Test adding a word score with a non-existent user
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.add_word_score(999, score_obj)  # Attempting to add a score for a non-existent user should raise an error

    def test_add_word_score_nonexistent_word_id(self):
        # Test adding a word score with a non-existent word_id
        self.db_manager.insert_user("test_user")
        score_obj = Score(999, 8)
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.add_word_score(1, score_obj)  # Attempting to add a score for a non-existent word_id should raise an error

    def test_add_word_score_incorrect_score(self):
        # Test adding a word score with an incorrect score
        self.db_manager.insert_user("test_user")
        word_list = [("cat", "NOUN", 10)]
        self.db_manager.add_words_to_db(word_list)
        score_neg = Score(1, (MIN_SCORE - 1))
        score_high = Score(1, (MAX_SCORE + 1))
        with self.assertRaises(ValueError):
            self.db_manager.add_word_score(1, score_neg)  # Attempting to add a negative score should raise an error
        with self.assertRaises(ValueError):
            self.db_manager.add_word_score(1, score_high)  # Attempting to add a score above the maximum should raise an error

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
        initial_scores = {Score(word_id=self.word_ids[0], score=5)}
        updated_scores = {Score(word_id=self.word_ids[0], score=7)}
        self.db_manager.update_user_scores(self.user_id, initial_scores)
        self.db_manager.update_user_scores(self.user_id, updated_scores)
        scores = self.db_manager.retrieve_user_scores(self.user_id)
        # Find and check the score
        score_dict = {score.word_id: score.score for score in scores}

        # Check the updated score
        self.assertEqual(score_dict[self.word_ids[0]], 7)

    def test_update_user_scores_multiple_scores_update(self):
        # Test adding three scores, then updating two of them
        initial_scores = {Score(word_id=self.word_ids[i], score=3 + i) for i in range(3)}
        updated_scores = {Score(word_id=self.word_ids[0], score=8), Score(word_id=self.word_ids[1], score=9)}
        self.db_manager.update_user_scores(self.user_id, initial_scores)
        self.db_manager.update_user_scores(self.user_id, updated_scores)
        scores = self.db_manager.retrieve_user_scores(self.user_id)
        # Find and check the scores
        score_dict = {score.word_id: score.score for score in scores}
        
        # Check the updated scores
        self.assertEqual(score_dict[self.word_ids[0]], 8)
        self.assertEqual(score_dict[self.word_ids[1]], 9)
        
        # Check the unchanged score
        unchanged_score_id = next(id for id in self.word_ids if id not in [s.word_id for s in updated_scores])
        self.assertEqual(score_dict[unchanged_score_id], 5)

    def test_update_user_scores_nonexistent_word(self):
        # Test updating with a word_id that does not exist
        scores = {Score(word_id=9999, score=7)}  # Assuming 9999 is an ID that does not exis
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.update_user_scores(self.user_id, scores)

    def test_update_user_scores_nonexistent_user(self):
        # Test updating a score for a non-existent user
        scores = {Score(word_id=self.word_ids[0], score=7)}
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
        score_1 = Score(word_ids[0], 5)
        score_2 = Score(word_ids[1], 8)
        self.db_manager.add_word_score(user_id, score_1)
        self.db_manager.add_word_score(user_id, score_2)

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
        self.assertIsInstance(scores, set)
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
        self.assertIsInstance(scores, set)
        self.assertEqual(len(scores), 0)

    def test_nonexistent_user(self):
        """
        Test retrieving scores for a nonexistent user.
        """
        with self.assertRaises(ValueDoesNotExistInDB):
            scores = self.db_manager.retrieve_user_scores(9999)  # Assuming 9999 is an ID that does not exist

class TestAddTemplate(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        self.db_manager = DatabaseManager(TEST_DB_FILE)
        self.db_manager.create_db()

    def tearDown(self):
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def test_add_template_with_two_parameters(self):
        """
        Test adding a template with two parameters.
        """
        # Create a template with two parameters
        template_string = (
            "Translate the following into English:\n" +
            "   '$sentence' and '$phrase'"
        )
        template_description = "Description of the template"
        template_examples = ["Example one", "Example two"]
        parameter_description = {
            "sentence": "Sentence in target language to be translated into English.",
            "phrase": "Phrase in target language to be translated into English."
        }

        test_template = TaskTemplate(
            target_language=Language.GERMAN,
            starting_language=Language.ENGLISH,
            template_string=template_string,
            template_description=template_description,
            template_examples=template_examples,
            parameter_description=parameter_description,
            task_type=TaskType.ONE_WAY_TRANSLATION
        )
        # Add the template
        added_template = self.db_manager.add_template(test_template)

        # Retrieve the template from the database
        retrieved_template = self.db_manager.get_template_by_id(added_template.id)

        # Verify that the retrieved template matches the added template
        self.assertIsNotNone(retrieved_template)
        self.assertEqual(retrieved_template.target_language.name, Language.GERMAN.name)
        self.assertEqual(retrieved_template.starting_language.name, Language.ENGLISH.name)
        self.assertEqual(retrieved_template.task_type.name, TaskType.ONE_WAY_TRANSLATION.name)
        self.assertEqual(retrieved_template.template.template, template_string)
        self.assertEqual(retrieved_template.template.template, template_string)
        self.assertEqual(retrieved_template.description, template_description)
        self.assertEqual(retrieved_template.examples, template_examples)
        self.assertEqual(retrieved_template.parameter_description, parameter_description)

    # def test_add_template_with_duplicate_template_string(self):
    #     """
    #     Test adding a template with a duplicate name.
    #     """
    #     # Add a template with a specific name to the database
    #     initial_template_name = "Test Template"
    #     template_id = self.db_manager.add_template(
    #         template_string="template_string_placeholder",
    #         template_description="template_description_placeholder",
    #         template_examples=["example1", "example2"],
    #         parameter_description={"param1": "param1_description", "param2": "param2_description"},
    #         task_type=TaskType.ONE_WAY_TRANSLATION
    #     )

    #     # Attempt to add another template with the same name
    #     with self.assertRaises(ValueError):
    #         self.db_manager.add_template(
    #             template_string="template_string_placeholder",
    #             template_description="template_description_placeholder",
    #             template_examples=["example1", "example2"],
    #             parameter_description={"param1": "param1_description", "param2": "param2_description"},
    #             task_type=TaskType.ONE_WAY_TRANSLATION
    #         )

class TestAddResourceManual(unittest.TestCase):

    def get_test_word_ids(self):
        """
        Helper method to retrieve test user and word IDs.
        This method now returns a list of word IDs to handle multiple words.
        """
        word_ids = [
            self.db_manager.connection.execute("SELECT id FROM words WHERE word=?", ("word1",)).fetchone()[0],
            self.db_manager.connection.execute("SELECT id FROM words WHERE word=?", ("word2",)).fetchone()[0]
        ]
        return word_ids

    def setUp(self):
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        self.db_manager = DatabaseManager(TEST_DB_FILE)
        self.db_manager.create_db()

        # Create some sample LexicalItem objects
        # TODO add words to database first and get the words ids first 

        self.db_manager.add_words_to_db([
            ("word1", "noun", 10),
            ("word2", "verb", 8)
        ])

        ids = self.get_test_word_ids()
        self.lexical_item_1 = LexicalItem(item="word1", pos="noun", freq=10, id=ids[0])
        self.lexical_item_2 = LexicalItem(item="word2", pos="verb", freq=8, id=ids[1])

    def tearDown(self):
        # Clean up resources after each test
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def test_add_resource_manual(self):
        # Define resource string and target words
        resource_str = "This is a sample resource string containing word1 and word2."
        target_words = {self.lexical_item_1, self.lexical_item_2}

        # Call the add_resource_manual function
        added_resource = self.db_manager.add_resource_manual(resource_str, target_words)

        # Check if the returned object is an instance of Resource
        self.assertIsInstance(added_resource, Resource)

        # Fetch the added resource from the database to verify its correctness
        fetched_resource = self.db_manager.get_resource_by_id(added_resource.resource_id)

        # Check if the fetched resource matches the added resource
        self.assertEqual(fetched_resource.resource, resource_str)
        print(fetched_resource.target_words)
        print(target_words)
        self.assertEqual(fetched_resource.target_words, target_words)

class TestAddTask(unittest.TestCase):
    def setUp(self):
        # Initialize the database manager and create the test database
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        self.db_manager = DatabaseManager(TEST_DB_FILE)
        self.db_manager.create_db()

    def tearDown(self):
        # Close the database connection and remove the test database file
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def test_add_task(self):
        # add template
        # Create a template with two parameters
        template_string = (
            "Translate the following into English:\n" +
            "   '$sentence' and '$phrase'"
        )
        template_description = "Description of the template"
        template_examples = ["Example one", "Example two"]
        parameter_description = {
            "sentence": "Sentence in target language to be translated into English.",
            "phrase": "Phrase in target language to be translated into English."
        }

        test_template = TaskTemplate(
            target_language=Language.GERMAN,
            starting_language=Language.ENGLISH,
            template_string=template_string,
            template_description=template_description,
            template_examples=template_examples,
            parameter_description=parameter_description,
            task_type=TaskType.ONE_WAY_TRANSLATION
        )

        # Add the template
        added_template = self.db_manager.add_template(test_template)
        # add words 

        self.db_manager.add_words_to_db([
            ("word1", "noun", 10),
            ("word2", "verb", 8)
        ])

        word_ids = [
            self.db_manager.connection.execute("SELECT id FROM words WHERE word=?", ("word1",)).fetchone()[0],
            self.db_manager.connection.execute("SELECT id FROM words WHERE word=?", ("word2",)).fetchone()[0]
        ]

        words = {LexicalItem("word1", "noun", 10, word_ids[0]), LexicalItem("word2", "verb", 8, word_ids[1])}

        resource1 = self.db_manager.add_resource_manual('Resource 1', words)
        resource2 = self.db_manager.add_resource_manual('Resource 2', words)

        resources = {
            'sentence': resource1,
            'phrase': resource2
        }
        target_words = {
            LexicalItem(item='word1', pos='noun', freq=10, id=word_ids[0]),
            LexicalItem(item='word2', pos='verb', freq=8, id=word_ids[1])
        }
        answer = 'Sample answer'

        # Add the task to the database
        added_task = self.db_manager.add_task(added_template.id, resources, target_words, answer)

        # Assert that the returned task object is not None
        self.assertIsNotNone(added_task)

        # Fetch the added task from the database to verify its correctness
        fetched_task = self.db_manager.get_task_by_id(added_task.id)

        # Assert that the fetched task matches the added task
        self.assertEqual(fetched_task.template.id, added_template.id)
        self.assertEqual(fetched_task.resources, resources)
        self.assertEqual(fetched_task.learning_items, target_words)
        self.assertEqual(fetched_task.correctAnswer, answer)


class TestAddTask(unittest.TestCase):
    def setUp(self):
        # Initialize the database manager and create the test database
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        self.db_manager = DatabaseManager(TEST_DB_FILE)
        self.db_manager.create_db()

        # add user
        self.user_id = self.db_manager.insert_user("user1")

        # add template
        # Create a template with two parameters
        template_string = (
            "Translate the following into English:\n" +
            "   '$sentence' and '$phrase'"
        )
        template_description = "Description of the template"
        template_examples = ["Example one", "Example two"]
        parameter_description = {
            "sentence": "Sentence in target language to be translated into English.",
            "phrase": "Phrase in target language to be translated into English."
        }
        test_template = TaskTemplate(
            target_language=Language.GERMAN,
            starting_language=Language.ENGLISH,
            template_string=template_string,
            template_description=template_description,
            template_examples=template_examples,
            parameter_description=parameter_description,
            task_type=TaskType.ONE_WAY_TRANSLATION
        )

        # Add the template
        self.added_template = self.db_manager.add_template(test_template)
        # add words 
        self.db_manager.add_words_to_db([
            ("word1", "noun", 10),
            ("word2", "verb", 8)
        ])

        self.word_ids = [
            self.db_manager.connection.execute("SELECT id FROM words WHERE word=?", ("word1",)).fetchone()[0],
            self.db_manager.connection.execute("SELECT id FROM words WHERE word=?", ("word2",)).fetchone()[0]
        ]

        self.words = {LexicalItem("word1", "noun", 10, self.word_ids[0]), LexicalItem("word2", "verb", 8, self.word_ids[1])}
        


    def tearDown(self):
        # Close the database connection and remove the test database file
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def create_example_task(self, resource_string1, resource_string2):
        target_words = {
            LexicalItem(item='word1', pos='noun', freq=10, id=self.word_ids[0]),
            LexicalItem(item='word2', pos='verb', freq=8, id=self.word_ids[1])
        }
        answer = 'Sample answer'
        resource1 = self.db_manager.add_resource_manual(resource_string1, self.words)
        resource2 = self.db_manager.add_resource_manual(resource_string2, self.words)
        resources = {
            'sentence': resource1,
            'phrase': resource2
        }
        task = self.db_manager.add_task(self.added_template.id, resources, target_words, answer)
        return task

    def test_add_user_lesson_data(self):
        task1 = self.create_example_task("task1-r1", "task1-r2")
        task2 = self.create_example_task("task2-r1", "task2-r2")
        task3 = self.create_example_task("task3-r1", "task3-r2")

        evaluation1 = Evaluation()
        evaluation1.add_entry(
            task1,
            "response1",
            {Score(1,4)}
        )
        evaluation1.add_entry(
            task2,
            "response2",
            {Score(1,6)}
        )
        evaluation2 = Evaluation()
        evaluation2.add_entry(
            task3,
            "response3",
            {Score(1,5), Score(2,7)}
        )

        lesson_data = [evaluation1, evaluation2]

        self.db_manager.save_user_lesson_data(self.user_id, lesson_data)

        conn = self.db_manager.connection

        # Validate the insertion of user lesson data
        # Check user_lessons
        lesson_rows = list(conn.execute("SELECT id, user_id FROM user_lessons"))
        self.assertEqual(len(lesson_rows), 1)
        self.assertEqual(lesson_rows[0][1], self.user_id)

        # Check evaluations
        evaluation_rows = list(conn.execute("SELECT lesson_id, sequence_number, id FROM evaluations WHERE lesson_id=? ORDER BY sequence_number", (lesson_rows[0][0],)))
        print(evaluation_rows)
        self.assertEqual(len(evaluation_rows), len(lesson_data))
        for i, evaluation in enumerate(evaluation_rows):
            self.assertEqual(evaluation[1], i + 1)  # Check sequence number

        # Check history_entries and entry_scores
        for i, evaluation in enumerate(lesson_data):
            history_entries = list(conn.execute("SELECT evaluation_id, task_id, response, id FROM history_entries WHERE evaluation_id=?", (evaluation_rows[i][2],)))
            print(history_entries)
            self.assertEqual(len(history_entries), len(evaluation.history))

            for j, history_entry in enumerate(evaluation.history):
                print(history_entries[j])
                self.assertEqual(history_entries[j][2], history_entry.response)  # Check response text
                self.assertEqual(history_entries[j][1], history_entry.task.id)  # Check task ID

                # Check scores
                scores_rows = list(conn.execute("SELECT word_id, score FROM entry_scores WHERE history_entry_id=?", (history_entries[j][3],)))
                scores_dict = {score.word_id: score.score for score in history_entry.evaluation_result}

                self.assertEqual(len(scores_rows), len(history_entry.evaluation_result))

                for score_row in scores_rows:
                    print(score_row)
                    print(scores_dict)
                    self.assertEqual(score_row[1], scores_dict[score_row[0]])



if __name__ == '__main__':
    unittest.main()
