import json
from typing import Dict
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

class TestUpdateUserScores(unittest.TestCase):
    def setUp(self):
        # Ensure the test database does not exist before starting each test
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        
        # Initialize the database manager
        self.db_manager = DatabaseManager(TEST_DB_FILE)

        # Insert a test user and predefined words
        user_id = self.db_manager.insert_user("test_user")
        word_list = [("word1", "noun", 1), ("word2", "verb", 2), ("word3", "adj", 3)]
        word_ids = self.db_manager.add_words_to_db(word_list)

        # Store user_id and word_ids for use in tests
        self.user_id = user_id
        self.word_ids = word_ids

    def tearDown(self):
        # Close the database session and delete the test database file
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def test_update_user_scores_single_score_update(self):
        # Test adding a single score and updating it
        initial_scores = {Score(word_id=self.word_ids[0], score=5)}
        updated_scores = {Score(word_id=self.word_ids[0], score=7)}
        self.db_manager.update_user_scores(self.user_id, initial_scores)
        self.db_manager.update_user_scores(self.user_id, updated_scores)
        score = self.db_manager.get_score(self.user_id, self.word_ids[0])

        # Assert that the score is updated correctly
        self.assertEqual(score, updated_scores.pop().score)

    def test_update_user_scores_multiple_scores_update(self):
        # Prepare the initial and updated scores
        initial_scores = {Score(word_id=id, score=3 + i) for i, id in enumerate(self.word_ids)}
        updated_scores = {Score(word_id=self.word_ids[0], score=8), Score(word_id=self.word_ids[1], score=9)}
        
        # Apply the initial scores to the database
        self.db_manager.update_user_scores(self.user_id, initial_scores)
        
        # Update the scores with the new values
        self.db_manager.update_user_scores(self.user_id, updated_scores)
        
        # Retrieve the scores from the database
        actual_scores_dict = self.db_manager.retrieve_user_scores(self.user_id)
        
        # Convert dictionary to set of Scores for easier comparison
        actual_scores = set(actual_scores_dict.values())

        # Prepare the expected scores set
        expected_scores = updated_scores.union({Score(word_id=self.word_ids[2], score=5)})  # Include the unchanged score
        
        # Assert that the sets are equal, confirming both updates and non-changes
        self.assertEqual(actual_scores, expected_scores)


    def test_update_user_scores_nonexistent_word(self):
        # Test updating scores for a non-existent word
        scores = {Score(word_id=9999, score=7)}  # Assuming 9999 does not exist
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.update_user_scores(self.user_id, scores)

    def test_update_user_scores_nonexistent_user(self):
        # Test updating scores for a non-existent user
        scores = {Score(word_id=self.word_ids[0], score=7)}
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.update_user_scores(9999, scores)  # Assuming 9999 is a non-existent user ID

class TestRetrieveUserScores(unittest.TestCase):
    def setUp(self):
        """
        Set up the environment before each test.
        """
        self.db_manager = DatabaseManager(TEST_DB_FILE)

        # Insert test data
        user_id = self.db_manager.insert_user("test_user")
        word_ids = self.db_manager.add_words_to_db([("test", "noun", 1), ("study", "verb", 2)])
        
        # Add scores for both words for the user
        self.db_manager.add_word_score(user_id, Score(word_ids[0], 5))
        self.db_manager.add_word_score(user_id, Score(word_ids[1], 8))

        self.user_id = user_id
        self.word_ids = word_ids

    def tearDown(self):
        # Close the database session and delete the test database file
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def test_user_with_scores(self):
        """
        Test retrieving scores for a user with existing scores.
        """
        scores = self.db_manager.retrieve_user_scores(self.user_id)
        self.assertIsInstance(scores, dict)
        self.assertEqual(len(scores), 2)  # Expecting scores for 2 words
        # Check specific scores
        self.assertEqual(scores.get(self.word_ids[0]).score, 5)
        self.assertEqual(scores.get(self.word_ids[1]).score, 8)

    def test_user_without_scores(self):
        """
        Test retrieving scores for a user without scores.
        """
        another_user_id = self.db_manager.insert_user("another_user")
        scores = self.db_manager.retrieve_user_scores(another_user_id)
        self.assertIsInstance(scores, dict)
        self.assertEqual(len(scores), 0)

    def test_nonexistent_user(self):
        """
        Test retrieving scores for a nonexistent user.
        """
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.retrieve_user_scores(9999)  # Assuming 9999 is an ID that does not exist

class TestTemplates(unittest.TestCase):
    def setUp(self):
        """
        Set up the environment before each test.
        """
        self.db_manager = DatabaseManager(TEST_DB_FILE)

        # Insert test data
        user_id = self.db_manager.insert_user("test_user")
        word_ids = self.db_manager.add_words_to_db([("test", "noun", 1), ("study", "verb", 2)])
        
        self.template_string = "test template string"
        self.template_description = "test description"
        self.template_examples = ["example 1", "example 2"]
        self.starting_language = "example language start"
        self.target_language = "example language target"
        self.parameter_description = {
            "sentence": "Sentence in target language to be translated into English.",
            "phrase": "Phrase in target language to be translated into English."
        }

        self.template = TaskTemplate(
            target_language=self.target_language,
            starting_language=self.starting_language,
            template_string=self.template_string,
            template_description=self.template_description,
            template_examples=self.template_examples,
            parameter_description=self.parameter_description,
            task_type=TaskType.ONE_WAY_TRANSLATION
        )

    def tearDown(self):
        # Close the database session and delete the test database file
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def test_add_get_template(self):
        # add template
        template_id = self.db_manager.add_template(self.template)
        
        # retrieve and check template
        retrieved_template = self.db_manager.get_template_by_id(template_id)

        # check the template
        self.assertEqual(retrieved_template.starting_language, self.template.starting_language)
        self.assertEqual(retrieved_template.target_language, self.template.target_language)
        self.assertEqual(retrieved_template.get_template_string(), self.template.get_template_string())
        self.assertEqual(retrieved_template.description, self.template.description)
        self.assertEqual(retrieved_template.examples, self.template.examples)
        self.assertEqual(retrieved_template.parameter_description, self.template.parameter_description)
        self.assertEqual(retrieved_template.task_type, self.template.task_type)



    def test_add_template_duplicate_template_string(self):
        template_2 = TaskTemplate(
            target_language=self.target_language + "blah",
            starting_language=self.starting_language + "blah",
            template_string=self.template_string, # keep the same
            template_description=self.template_description + "blah",
            template_examples=self.template_examples +  ["blah"],
            parameter_description={**self.parameter_description, **{"blah": "blah"}},
            task_type=TaskType.ONE_WAY_TRANSLATION
        )

        self.db_manager.add_template(self.template)
        with self.assertRaises(ValueError):
            self.db_manager.add_template(template_2)

    def test_add_template_incorrect_task_type(self):
        self.template.task_type = "blah"

        with self.assertRaises(ValueError):
            self.db_manager.add_template(self.template)

    # def test_add_template_repeated_parameter_name(self):
    #     template_2 = TaskTemplate(
    #         target_language=self.target_language + "blah",
    #         starting_language=self.starting_language + "blah",
    #         template_string=self.template_string, # keep the same
    #         template_description=self.template_description + "blah",
    #         template_examples=self.template_examples +  ["blah"],
    #         parameter_description={"one": "blah", "one":"bleh", "two": "blah"},
    #         task_type=TaskType.ONE_WAY_TRANSLATION
    #     )
    #     with self.assertRaises(ValueError):
    #         self.db_manager.add_template(template_2)

    def test_remove_template():
        pass

    def test_get_template_parameters(self):
        template_id = self.db_manager.add_template(self.template)
        template_params = self.db_manager.get_template_parameters(template_id)

        self.assertEqual(len(list(template_params.keys())), 2)
        self.assertEqual(set(list(template_params.keys())), set(list(self.template.parameter_description.keys())))
        keys = list(template_params.keys())
        self.assertEqual(template_params[keys[0]], self.template.parameter_description[keys[0]])
        self.assertEqual(template_params[keys[1]], self.template.parameter_description[keys[1]])

    def test_get_template_parameters_no_params(self):
        self.template.parameter_description = {}
        template_id = self.db_manager.add_template(self.template)
        template_params = self.db_manager.get_template_parameters(template_id)

        self.assertEqual(template_params, None)

    def test_get_template_by_task_type(self):
        templates = self.db_manager.get_templates_by_task_type(self.template.task_type)
        self.assertEqual(len(templates), 0)

        # TODO add function for equality of tempaltes

        self.db_manager.add_template(self.template)
        templates_1 = self.db_manager.get_templates_by_task_type(self.template.task_type)
        self.assertEqual(len(templates_1), 1)
        self.assertIsInstance(templates_1[0], TaskTemplate)

        template_2 = TaskTemplate(
            target_language=self.target_language + "blah",
            starting_language=self.starting_language + "blah",
            template_string=self.template_string + "blah",
            template_description=self.template_description + "blah",
            template_examples=self.template_examples +  ["blah"],
            parameter_description={**self.parameter_description, **{"blah": "blah"}},
            task_type=self.template.task_type
        )

        self.db_manager.add_template(template_2)
        templates_2 = self.db_manager.get_templates_by_task_type(template_2.task_type)
        self.assertEqual(len(templates_2), 2)
        self.assertIsInstance(templates_2[0], TaskTemplate)
        self.assertIsInstance(templates_2[1], TaskTemplate)

        #try non existent task type
        with self.assertRaises(ValueError):
            templates_2 = self.db_manager.get_templates_by_task_type("blah")

class TestResources(unittest.TestCase):
    def setUp(self):
        """
        Set up the environment before each test.
        """
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        self.db_manager = DatabaseManager(TEST_DB_FILE)

        # Insert test data
        self.user_id = self.db_manager.insert_user("test_user")
        self.word_ids = self.db_manager.add_words_to_db([("test", "noun", 1), ("study", "verb", 2)])
        self.word_1 = self.db_manager.get_word_by_id(1)
        self.word_2 = self.db_manager.get_word_by_id(2)

    def tearDown(self):
        # Close the database session and delete the test database file
        self.db_manager.close()
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def test_add_get_resource_manual(self):
        resourse_str = "test resourse"
        resource = self.db_manager.add_resource_manual(resourse_str, set([self.word_1, self.word_2]))

        retrieved_resource = self.db_manager.get_resource_by_id(resource.resource_id)

        self.assertEqual(retrieved_resource.resource, resource.resource)
        self.assertEqual(set(retrieved_resource.target_words), set(resource.target_words))
        self.assertEqual(retrieved_resource.resource_id, resource.resource_id)

    # def test_remove_resource(self):
    #     pass



    



    



