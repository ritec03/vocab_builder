from contextlib import contextmanager
from typing import Set
import unittest

from sqlalchemy import select
from app_factory import create_app
from data_structures import (
    MAX_SCORE,
    MAX_USER_NAME_LENGTH,
    MIN_SCORE,
    Language,
    LexicalItem,
    Score,
    TaskType,
)

from database_orm import (
    DatabaseManager,
    InvalidDelete,
    ValueDoesNotExistInDB,
)
from database_objects import (
    LearningDataDBObj,
    ResourceDBObj,
    ResourceWordDBObj,
    TaskDBObj,
    TaskResourceDBObj,
    TaskTargetWordDBObj,
    UserLessonDBObj,
    WordDBObj,
)
import os

from task import Task, get_task_type_class
from evaluation import Evaluation
from task_template import TaskTemplate

# Define a test database file path
TEST_DB_FILE = "test_database.db"

class TestMixin:
    def setUp(self):
        self.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        self.db_manager: DatabaseManager = self.app.db_manager
        with session_manager(self.db_manager):
            # Ensure the test database does not exist before starting each test
            if os.path.exists(TEST_DB_FILE):
                os.remove(TEST_DB_FILE)
            # Insert a test user and predefined words
            self.words_tuples = [
                ("apple", "NOUN", 50), ("quickly", "ADV", 30), ("happy", "ADJ", 40),
                ("run", "VERB", 60), ("blue", "ADJ", 20)
            ]
            self.word_ids = self.db_manager.add_words_to_db(self.words_tuples)
            self.user_id = self.db_manager.insert_user("test_user")

@contextmanager
def session_manager(db_manager: DatabaseManager):
    """
    Simple session manager to emulate app's call for 
    shutdown_session in between transactions.
    """
    try:
        yield
    finally:
        db_manager.shutdown_session()


# TestMixin should be inherited first to preserve instance variables
class TestDatabaseFunctions(TestMixin, unittest.TestCase):
    def test_insert_user(self):
        # Assert that the user is inserted successfully
        user = self.db_manager.get_user_by_id(self.user_id)
        self.assertIsNotNone(user)  # Check that a row is returned
        self.assertEqual(
            user.user_name, "test_user"
        )  # Check that the inserted user name matches

    def test_insert_duplicate_user(self):
        # Test inserting a user with the same user name (should fail)
        with self.assertRaises(ValueError):
            self.db_manager.insert_user(
                "test_user"
            )  # Inserting the same user name should raise IntegrityError

    def test_remove_user_success(self):
        with session_manager(self.db_manager):
            # Test removing an existing user
            self.db_manager.remove_user(self.user_id)
        # Assert that the user is removed successfully
        user = self.db_manager.get_user_by_id(self.user_id)
        self.assertIsNone(user)  # Check that no row is returned

    def test_remove_nonexistent_user(self):
        # Test removing a non-existent user
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.remove_user(
                999
            )  # Attempting to remove a non-existent user should raise an exception

    def test_add_user_invalid_name_type(self):
        # Test adding a user with a user name that is not a string
        with self.assertRaises(ValueError):
            self.db_manager.insert_user(
                123
            )  # Inserting a non-string user name should raise a ValueError

    def test_add_user_long_name(self):
        # Test adding a user with a user name that is too long
        long_username = "a" * (
            MAX_USER_NAME_LENGTH + 1
        )  # Create a user name longer than MAX_USER_NAME_LENGTH
        with self.assertRaises(ValueError):
            self.db_manager.insert_user(
                long_username
            )  # Inserting a long user name should raise a ValueError

    def test_add_two_word_entries(self):
        # Test adding two word entries to the words table successfully
        test_words = {"cat": ("cat", "NOUN", 10), "dog": ("dog", "NOUN", 5)}
        with session_manager(self.db_manager):
            word_ids = self.db_manager.add_words_to_db(list(test_words.values()))

        # Assert that the entries are added successfully

        for id in word_ids:
            word = self.db_manager.get_word_by_id(id)
            test_word = test_words[word.item]
            self.assertEqual(word.item, test_word[0])
            self.assertEqual(word.pos, test_word[1])
            self.assertEqual(word.freq, test_word[2])

        self.assertEqual(
            len(word_ids), len(list(test_words.values()))
        )  # Check that there are no entires left

    def test_update_existing_word_entry(self):
        # Test updating an existing word/pos entry in the words table
        OLD_FREQ = 10
        NEW_FREQ = 15
        with session_manager(self.db_manager):
            word_list = [("cat", "NOUN", OLD_FREQ)]
            self.db_manager.add_words_to_db(word_list)  # Add initial entry
        with session_manager(self.db_manager):
            word_list_update = [("cat", "NOUN", NEW_FREQ)]
            word_ids = self.db_manager.add_words_to_db(word_list_update)  # Update frequency

        # Assert that the frequency is updated
        word = self.db_manager.get_word_by_id(word_ids[0])
        self.assertEqual(
            word.freq, NEW_FREQ
        )  # Check that the frequency is updated to NEW_FREQ

    def test_add_existing_word_entry(self):
        # Test adding an existing word/pos entry to the words table
        new_freq = self.words_tuples[0][2] + 10
        word_pos_duplicate = [(self.words_tuples[0][0], self.words_tuples[0][1], new_freq)]
        with session_manager(self.db_manager):
            word_ids = self.db_manager.add_words_to_db(
                word_pos_duplicate
            )  # Attempt to add the same entry again

        # Assert that only one word exists and only its freq is updated
        word = self.db_manager.get_word_by_id(word_ids[0])
        self.assertEqual(word.freq, new_freq)  # Check that the frequency remains 10
        # Assert that no new rows are added
        with self.db_manager.Session() as session:
            all_words = session.execute(
                select(WordDBObj)
            ).all()  # TODO remove sqlalchemy code
            self.assertEqual(len(all_words), len(self.word_ids))  # Ensure only one word entry exists

    def test_add_word_score(self):
        word = self.db_manager.get_word_by_id(self.word_ids[0])
        score_value = 8
        
        with session_manager(self.db_manager):
            # add lesson
            template_id = add_template(self.db_manager)
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, score_value)})
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with session_manager(self.db_manager):
            # add word score
            self.db_manager.add_word_score(self.user_id, Score(word.id, score_value), lesson_id)

        # Assert that the word score is added successfully
        with self.db_manager.Session() as session:
            entry = session.execute(
                select(LearningDataDBObj).where(
                    LearningDataDBObj.user_id == self.user_id,
                    LearningDataDBObj.word_id == word.id,
                    LearningDataDBObj.lesson_id == lesson_id
                )
            ).scalar()
            self.assertEqual(entry.score, score_value)  # Check that the score is 8

    def test_add_word_score_two_scores_for_word(self):
        word = self.db_manager.get_word_by_id(self.word_ids[0])

        with session_manager(self.db_manager):
            OLD_SCORE = 8
            NEW_SCORE = 5
            template_id = add_template(self.db_manager)

        with session_manager(self.db_manager):
            # add first lesson
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, OLD_SCORE)})
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with session_manager(self.db_manager):
            # Add old score
            self.db_manager.add_word_score(self.user_id, Score(word.id, OLD_SCORE), lesson_id)

        # Assert that the word score is added successfully
        score = self.db_manager.get_score(self.user_id, word.id, lesson_id)
        self.assertEqual(score, OLD_SCORE)  # Check that the score is OLD_SCORE

        with session_manager(self.db_manager):
            # add second lesson
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, NEW_SCORE)})
            lesson = [evaluation1]
            second_lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with session_manager(self.db_manager):
            # Add the next score for same word
            self.db_manager.add_word_score(self.user_id, Score(word.id, NEW_SCORE), second_lesson_id)

        # Assert that the second score was added
        updated_score = self.db_manager.get_score(self.user_id, word.id, second_lesson_id)
        self.assertEqual(updated_score, NEW_SCORE)  # Check that the score is NEW_SCORE

    def test_add_word_score_two_scores_for_word_same_lesson(self):
        word = self.db_manager.get_word_by_id(self.word_ids[0])

        with session_manager(self.db_manager):
            OLD_SCORE = 8
            NEW_SCORE = 5
            template_id = add_template(self.db_manager)

        with session_manager(self.db_manager):
            # add first lesson
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, OLD_SCORE)})
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with session_manager(self.db_manager):
            # Add old score
            self.db_manager.add_word_score(self.user_id, Score(word.id, OLD_SCORE), lesson_id)

        # Assert that the word score is added successfully
        score = self.db_manager.get_score(self.user_id, word.id, lesson_id)
        self.assertEqual(score, OLD_SCORE)  # Check that the score is OLD_SCORE

        with self.assertRaises(ValueDoesNotExistInDB):
            # Add the next score for same word
            self.db_manager.add_word_score(self.user_id, Score(word.id, NEW_SCORE), lesson_id)

    def test_add_word_score_no_lesson(self):
        word = self.db_manager.get_word_by_id(self.word_ids[0])
        score_value = 8
        non_existent_lesson_id = 999
        # add word score
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.add_word_score(self.user_id, Score(word.id, score_value), non_existent_lesson_id)


    def test_add_word_score_nonexistent_user(self):
        word = self.db_manager.get_word_by_id(self.word_ids[0])
        score_value = 8
        
        with session_manager(self.db_manager):
            # add lesson
            template_id = add_template(self.db_manager)
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, score_value)})
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with self.assertRaises(ValueDoesNotExistInDB):
            # add word score
            self.db_manager.add_word_score(999, Score(word.id, score_value), lesson_id)

    def test_add_word_score_nonexistent_word_id(self):
        word = self.db_manager.get_word_by_id(self.word_ids[0])
        score_value = 8
        
        with session_manager(self.db_manager):
            # add lesson
            template_id = add_template(self.db_manager)
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, score_value)})
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with self.assertRaises(ValueDoesNotExistInDB):
            # add word score
            self.db_manager.add_word_score(self.user_id, Score(999, score_value), lesson_id)

    def test_add_word_score_incorrect_score(self):
        word = self.db_manager.get_word_by_id(self.word_ids[0])
        score_value = 8
        
        with session_manager(self.db_manager):
            # add lesson
            template_id = add_template(self.db_manager)
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, score_value)})
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)
      
        # Test adding a word score with an incorrect score
        with self.assertRaises(ValueError):
            self.db_manager.add_word_score(
                self.user_id, Score(word.id, MIN_SCORE - 1), lesson_id
            )  # Attempting to add a negative score should raise an error
        with self.assertRaises(ValueError):
            self.db_manager.add_word_score(
                self.user_id, Score(word.id, MAX_SCORE + 1), lesson_id
            )  # Attempting to add a score above the maximum should raise an error


class TestUpdateUserScores(TestMixin, unittest.TestCase):
    def test_update_user_scores_two_scores_for_word(self):
        word = self.db_manager.get_word_by_id(self.word_ids[0])
        word_1 = self.db_manager.get_word_by_id(self.word_ids[1])

        OLD_SCORE = 8
        OLD_SCORE_1 = 4
        NEW_SCORE = 5
        NEW_SCORE_1 = 7
        with session_manager(self.db_manager):
            template_id = add_template(self.db_manager)

        with session_manager(self.db_manager):
            # add first lesson
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, OLD_SCORE)})
            evaluation1.add_entry(task, "response2", {Score(word_1.id, OLD_SCORE_1)})
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with session_manager(self.db_manager):
            # add second lesson
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, NEW_SCORE)})
            evaluation1.add_entry(task, "response2", {Score(word_1.id, NEW_SCORE_1)})
            lesson = [evaluation1]
            second_lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with session_manager(self.db_manager):
            # Add old score
            self.db_manager.update_user_scores(self.user_id, {Score(word.id, OLD_SCORE), Score(word_1.id, OLD_SCORE_1)}, lesson_id)
            self.db_manager.update_user_scores(self.user_id, {Score(word.id, NEW_SCORE), Score(word_1.id, NEW_SCORE_1)}, second_lesson_id)

        # Assert that the word score is added successfully
        score = self.db_manager.get_score(self.user_id, word.id, lesson_id)
        self.assertEqual(score, OLD_SCORE)  # Check that the score is OLD_SCORE
        score = self.db_manager.get_score(self.user_id, word_1.id, lesson_id)
        self.assertEqual(score, OLD_SCORE_1)  # Check that the score is OLD_SCORE

        # Assert that the second score was added
        updated_score = self.db_manager.get_score(self.user_id, word.id, second_lesson_id)
        self.assertEqual(updated_score, NEW_SCORE)  # Check that the score is NEW_SCORE
        updated_score = self.db_manager.get_score(self.user_id, word_1.id, second_lesson_id)
        self.assertEqual(updated_score, NEW_SCORE_1)  # Check that the score is NEW_SCORE

    def test_update_user_scores_two_scores_for_word_same_lesson(self):
        word = self.db_manager.get_word_by_id(self.word_ids[0])

        with session_manager(self.db_manager):
            OLD_SCORE = 8
            NEW_SCORE = 5
            template_id = add_template(self.db_manager)

        with session_manager(self.db_manager):
            # add first lesson
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, OLD_SCORE)})
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with session_manager(self.db_manager):
            # add second lesson
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, NEW_SCORE)})
            lesson = [evaluation1]
            second_lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with self.assertRaises(ValueDoesNotExistInDB):
            # Add old score
            self.db_manager.update_user_scores(self.user_id, {Score(word.id, OLD_SCORE), Score(word.id, NEW_SCORE)}, lesson_id)

    def test_update_user_scores_nonexistent_word(self):
        word = self.db_manager.get_word_by_id(self.word_ids[0])
        score_value = 8
        
        with session_manager(self.db_manager):
            # add lesson
            template_id = add_template(self.db_manager)
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, score_value)})
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with self.assertRaises(ValueDoesNotExistInDB):
            # add word score
            self.db_manager.update_user_scores(self.user_id, {Score(999, score_value)}, lesson_id)


    def test_update_user_scores_nonexistent_user(self):
        word = self.db_manager.get_word_by_id(self.word_ids[0])
        score_value = 8

        with session_manager(self.db_manager):        
            # add lesson
            template_id = add_template(self.db_manager)
            task = create_example_task(self.db_manager, "blah", "blah", {word}, template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(word.id, score_value)})
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with self.assertRaises(ValueDoesNotExistInDB):
            # add word score
            self.db_manager.update_user_scores(999, {Score(word.id, score_value)}, lesson_id)

class TestRetrieveUserScores(TestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        with session_manager(self.db_manager):
            self.template_id = add_template(self.db_manager)
            # add first lesson
            self.word_1 = self.db_manager.get_word_by_id(self.word_ids[0])
            self.word_2 = self.db_manager.get_word_by_id(self.word_ids[2])

        with session_manager(self.db_manager):
            task = create_example_task(self.db_manager, "blah", "blah", {self.word_1, self.word_2}, self.template_id)
            evaluation1 = Evaluation()
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)

        with session_manager(self.db_manager):
            self.db_manager.add_word_score(self.user_id, Score(self.word_1.id, 5), lesson_id)
            self.db_manager.add_word_score(self.user_id, Score(self.word_2.id, 8), lesson_id)

    def test_user_with_scores(self):
        """
        Test retrieving scores for a user with existing scores.
        """
        scores = self.db_manager.get_latest_word_score_for_user(self.user_id)
        self.assertIsInstance(scores, dict)
        self.assertEqual(len(scores), 2)  # Expecting scores for 2 words
        # Check specific scores
        self.assertEqual(scores.get(self.word_1.id)["score"].score, 5)
        self.assertEqual(scores.get(self.word_2.id)["score"].score, 8)

    def test_two_scores_one_updated(self):
        with session_manager(self.db_manager):
            NEW_SCORE = 1
            task = create_example_task(self.db_manager, "blah", "blah", {self.word_1, self.word_2}, self.template_id)
        with session_manager(self.db_manager):
            evaluation1 = Evaluation()
            lesson = [evaluation1]
            new_lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)
        with session_manager(self.db_manager):
            self.db_manager.add_word_score(self.user_id, Score(self.word_1.id, NEW_SCORE), new_lesson_id)
        
        scores = self.db_manager.get_latest_word_score_for_user(self.user_id)
        self.assertIsInstance(scores, dict)
        self.assertEqual(len(scores), 2)  # Expecting scores for 2 words
        # Check specific scores
        self.assertEqual(scores.get(self.word_1.id)["score"].score, NEW_SCORE)
        self.assertEqual(scores.get(self.word_2.id)["score"].score, 8)

    def test_user_without_scores(self):
        """
        Test retrieving scores for a user without scores.
        """
        with session_manager(self.db_manager):
            another_user_id = self.db_manager.insert_user("another_user")
        scores = self.db_manager.get_latest_word_score_for_user(another_user_id)
        self.assertIsInstance(scores, dict)
        self.assertEqual(len(scores), 0)

    def test_nonexistent_user(self):
        """
        Test retrieving scores for a nonexistent user.
        """
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.get_latest_word_score_for_user(
                9999
            )  # Assuming 9999 is an ID that does not exist


class TestTemplates(TestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.template_string = "test template string"
        self.template_description = "test description"
        self.template_examples = ["example 1", "example 2"]
        self.starting_language = Language.ENGLISH
        self.target_language = Language.GERMAN
        self.parameter_description = {
            "sentence": "Sentence in target language to be translated into English.",
            "phrase": "Phrase in target language to be translated into English.",
        }

        self.template = TaskTemplate(
            target_language=self.target_language,
            starting_language=self.starting_language,
            template_string=self.template_string,
            template_description=self.template_description,
            template_examples=self.template_examples,
            parameter_description=self.parameter_description,
            task_type=TaskType.ONE_WAY_TRANSLATION,
        )

    def test_add_get_template(self):
        with session_manager(self.db_manager):
            # add template
            template_id = self.db_manager.add_template(self.template)

        # retrieve and check template
        retrieved_template = self.db_manager.get_template_by_id(template_id)

        # check the template
        self.assertEqual(
            retrieved_template.starting_language, self.template.starting_language
        )
        self.assertEqual(
            retrieved_template.target_language, self.template.target_language
        )
        self.assertEqual(
            retrieved_template.get_template_string(),
            self.template.get_template_string(),
        )
        self.assertEqual(retrieved_template.description, self.template.description)
        self.assertEqual(retrieved_template.examples, self.template.examples)
        self.assertEqual(
            retrieved_template.parameter_description,
            self.template.parameter_description,
        )
        self.assertEqual(retrieved_template.task_type, self.template.task_type)

    def test_add_template_duplicate_template_string(self):
        template_2 = TaskTemplate(
            target_language=self.target_language,
            starting_language=self.starting_language,
            template_string=self.template_string,  # keep the same
            template_description=self.template_description + "blah",
            template_examples=self.template_examples + ["blah"],
            parameter_description={**self.parameter_description, **{"blah": "blah"}},
            task_type=TaskType.ONE_WAY_TRANSLATION,
        )

        with session_manager(self.db_manager):
            self.db_manager.add_template(self.template)

        with self.assertRaises(ValueError):
            self.db_manager.add_template(template_2)

    def test_add_template_incorrect_task_type(self):
        self.template.task_type = "blah"

        with self.assertRaises(ValueError):
            self.db_manager.add_template(self.template)

    # TODO see how to test that
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

    # TODO complete the remove template tests
    # def test_remove_template(self):
    #     self.fail()

    def test_get_template_parameters(self):
        with session_manager(self.db_manager):
            template_id = self.db_manager.add_template(self.template)

        template_params = self.db_manager.get_template_parameters(template_id)

        self.assertEqual(len(list(template_params.keys())), 2)
        self.assertEqual(
            set(list(template_params.keys())),
            set(list(self.template.parameter_description.keys())),
        )
        keys = list(template_params.keys())
        self.assertEqual(
            template_params[keys[0]], self.template.parameter_description[keys[0]]
        )
        self.assertEqual(
            template_params[keys[1]], self.template.parameter_description[keys[1]]
        )

    def test_get_template_parameters_no_params(self):
        with session_manager(self.db_manager):
            self.template.parameter_description = {}
            template_id = self.db_manager.add_template(self.template)
        template_params = self.db_manager.get_template_parameters(template_id)

        self.assertEqual(template_params, None)

    def test_get_template_by_task_type(self):
        templates = self.db_manager.get_templates_by_task_type(self.template.task_type)
        self.assertEqual(len(templates), 0)

        # TODO add function for equality of tempaltes

        with session_manager(self.db_manager):    
            self.db_manager.add_template(self.template)

        templates_1 = self.db_manager.get_templates_by_task_type(
            self.template.task_type
        )
        self.assertEqual(len(templates_1), 1)
        self.assertIsInstance(templates_1[0], TaskTemplate)

        template_2 = TaskTemplate(
            target_language=self.target_language,
            starting_language=self.starting_language,
            template_string=self.template_string + "blah",
            template_description=self.template_description + "blah",
            template_examples=self.template_examples + ["blah"],
            parameter_description={**self.parameter_description, **{"blah": "blah"}},
            task_type=self.template.task_type,
        )
        with session_manager(self.db_manager):
            self.db_manager.add_template(template_2)

        templates_2 = self.db_manager.get_templates_by_task_type(template_2.task_type)
        self.assertEqual(len(templates_2), 2)
        self.assertIsInstance(templates_2[0], TaskTemplate)
        self.assertIsInstance(templates_2[1], TaskTemplate)

        # try non existent task type
        with self.assertRaises(ValueError):
            templates_2 = self.db_manager.get_templates_by_task_type("blah")


class TestResources(TestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.word_1 = self.db_manager.get_word_by_id(1)
        self.word_2 = self.db_manager.get_word_by_id(2)

    def test_add_get_resource_manual(self):
        with session_manager(self.db_manager):
            resourse_str = "test resourse"
            resource = self.db_manager.add_resource_manual(
                resourse_str, set([self.word_1, self.word_2])
            )

        retrieved_resource = self.db_manager.get_resource_by_id(resource.resource_id)

        self.assertEqual(retrieved_resource.resource, resource.resource)
        self.assertEqual(
            set(retrieved_resource.target_words), set(resource.target_words)
        )
        self.assertEqual(retrieved_resource.resource_id, resource.resource_id)

    def test_resources_by_target_word(self):
        with session_manager(self.db_manager):
            target_word = self.word_1
            # add resource
            resource1 = self.db_manager.add_resource_manual(
                "resourse_str1", set([self.word_1, self.word_2])
            )
            resource2 = self.db_manager.add_resource_manual(
                "resourse_str2", set([self.word_2])
            )

        retrieved_resources = self.db_manager.get_resources_by_target_word(target_word)
        self.assertEqual(len(retrieved_resources), 1)
        self.assertEqual(retrieved_resources[0].resource_id, resource1.resource_id)

    def test_resources_by_target_word_none(self):
        with session_manager(self.db_manager):
            target_word = self.word_1
            # add resource
            resource1 = self.db_manager.add_resource_manual(
                "resourse_str1", set([self.word_2])
            )
            resource2 = self.db_manager.add_resource_manual(
                "resourse_str2", set([self.word_2])
            )

        retrieved_resources = self.db_manager.get_resources_by_target_word(target_word)
        self.assertEqual(len(retrieved_resources), 0)

    def test_remove_resource_no_associated_tasks(self):
        with session_manager(self.db_manager):
            # add two resources
            resource1 = self.db_manager.add_resource_manual(
                "resourse_str1", set([self.word_2])
            )
            resource2 = self.db_manager.add_resource_manual(
                "resourse_str2", set([self.word_2])
            )

        with session_manager(self.db_manager):
            # remove a resource
            self.db_manager.remove_resource(resource1.resource_id)

        # check
        with self.db_manager.Session() as session:
            resources = session.scalars(select(ResourceDBObj)).all()
            self.assertEqual(len(resources), 1)

            removed_resource = self.db_manager.get_resource_by_id(resource1.resource_id)
            self.assertEqual(removed_resource, None)

            # assert there are no resource words associated with removed resource
            remaining_resource_words = session.scalars(
                select(ResourceWordDBObj).where(
                    ResourceWordDBObj.resource_id == resource1.resource_id
                )
            ).all()
            self.assertEqual(
                len(remaining_resource_words),
                0,
                "No resource words should remain for the deleted resource",
            )

    def test_remove_resource_with_associated_tasks(self):
        with session_manager(self.db_manager):
            # add two resources
            resource1 = self.db_manager.add_resource_manual(
                "resourse_str1", set([self.word_2])
            )
            resource2 = self.db_manager.add_resource_manual(
                "resourse_str2", set([self.word_2])
            )

        with session_manager(self.db_manager):
            # associate task with resource 1
            template = TaskTemplate(
                target_language=Language.GERMAN,
                starting_language=Language.ENGLISH,
                template_string="blah",
                template_description="blah",
                template_examples=["eg1"],
                parameter_description={"sentence": "blah"},
                task_type=TaskType.ONE_WAY_TRANSLATION,
            )
            template_id = self.db_manager.add_template(template)
            template.id = template_id
            resources = {"sentence": resource1}
            self.db_manager.add_task(template_id, resources, {self.word_1}, "answer")

        # remove a resource
        with self.assertRaises(InvalidDelete):
            self.db_manager.remove_resource(resource1.resource_id)


class TestTasks(TestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.word_1 = self.db_manager.get_word_by_id(1)
        self.word_2 = self.db_manager.get_word_by_id(2)

        # add template
        self.template_string = "test template string"
        self.template_description = "test description"
        self.template_examples = ["example 1", "example 2"]
        self.starting_language = Language.ENGLISH
        self.target_language = Language.GERMAN
        self.parameter_description = {
            "sentence": "Sentence in target language to be translated into English.",
            "phrase": "Phrase in target language to be translated into English.",
        }

        self.template = TaskTemplate(
            target_language=self.target_language,
            starting_language=self.starting_language,
            template_string=self.template_string,
            template_description=self.template_description,
            template_examples=self.template_examples,
            parameter_description=self.parameter_description,
            task_type=TaskType.ONE_WAY_TRANSLATION,
        )
        with session_manager(self.db_manager):
            self.template_id = self.db_manager.add_template(self.template)
        self.template.id = self.template_id

        with session_manager(self.db_manager):
            # add test resources
            self.resource1 = self.db_manager.add_resource_manual(
                "test resource 1", set([self.word_1])
            )
            self.resource2 = self.db_manager.add_resource_manual(
                "test resource 2", set([self.word_2])
            )
        self.resources = {"sentence": self.resource1, "phrase": self.resource2}

        self.template2 = TaskTemplate(
            target_language=self.target_language,
            starting_language=self.starting_language,
            template_string="Which of the following coorectly translates the word \"$target_word\" into English?\n  a. '$A'\n   b. '$B'\n   c. '$C'\n   d. '$D'",
            template_description="description",
            template_examples=self.template_examples,
            parameter_description={
                "target_word": "Word in the target language to be practiced in this task.",
                "A": "Option a of the multiple choice question.",
                "B": "Option b of the multiple choice question.",
                "C": "Option c of the multiple choice question.",
                "D": "Option d of the multiple choice question.",
            },
            task_type=TaskType.FOUR_CHOICE,
        )

        self.four_choice_resources = {
            "target_word": self.resource1,
            "A": self.resource2,
            "B": self.resource2,
            "C": self.resource2,
            "D": self.resource2,
        }
        with session_manager(self.db_manager):
            self.template2_id = self.db_manager.add_template(self.template2)

    def test_add_and_get_task(self):
        """
        Test adding a task to the database and retrieving it to verify that the addition and retrieval are correct.
        """
        target_words = set([self.word_1, self.word_2])
        answer = "The correct translation"

        with session_manager(self.db_manager):
            # Add the task to the database
            task = self.db_manager.add_task(
                template_id=self.template_id,
                resources=self.resources,
                target_words=target_words,
                answer=answer,
            )

        # Retrieve the task by ID
        retrieved_task = self.db_manager.get_task_by_id(task.id)

        # Check that the retrieved task matches the added task
        self.assertEqual(retrieved_task.id, task.id)
        self.assertEqual(retrieved_task.template.id, task.template.id)
        self.assertEqual(retrieved_task.correctAnswer, answer)

        # Check the resources and target words are correctly associated
        self.assertEqual(
            set(retrieved_task.resources.keys()), set(self.resources.keys())
        )
        self.assertEqual(
            set(lexical_item.id for lexical_item in retrieved_task.learning_items),
            set(word.id for word in target_words),
        )

    def test_get_tasks_by_type(self):
        """
        Test by adding three tasks with two tasks of same task type and returning those.
        """
        with session_manager(self.db_manager):
            self.db_manager.add_task(
                template_id=self.template2_id,
                resources=self.four_choice_resources,
                target_words=set(),
                answer="A",
            )
        with session_manager(self.db_manager):
            self.db_manager.add_task(
                template_id=self.template_id,
                resources=self.resources,
                target_words=set(),
                answer="Answer 2",
            )
        with session_manager(self.db_manager):
            self.db_manager.add_task(
                template_id=self.template2_id,
                resources=self.four_choice_resources,
                target_words=set(),
                answer="B",
            )

        # Fetch tasks by type
        tasks = self.db_manager.get_tasks_by_type(self.template2.task_type)
        self.assertEqual(len(tasks), 2)  # Two tasks should be of type one

        # Assert
        for task in tasks:
            self.assertIsInstance(task, get_task_type_class(self.template2.task_type))
            self.assertEqual(task.template.task_type, self.template2.task_type)

    def test_get_tasks_by_type_no_tasks(self):
        """
        Test by adding tasks and returning zero tasks for a non-existent type.
        """
        task_type = TaskType.FOUR_CHOICE
        # Assuming TaskType.FOUR_CHOICE was not used in added tasks or no tasks added
        tasks = self.db_manager.get_tasks_by_type(task_type)
        self.assertEqual(len(tasks), 0)  # No tasks should be returned

    def test_get_tasks_by_type_invalid_task_type(self):
        """
        Test by trying to get tasks of an invalid task type.
        """
        with self.assertRaises(ValueError):
            self.db_manager.get_tasks_by_type("InvalidType")

    def test_get_tasks_by_template(self):
        """
        Test the case when two tasks are returned from a database with three tasks.
        """
        # Add multiple tasks with different templates

        with session_manager(self.db_manager):
            self.db_manager.add_task(
                template_id=self.template_id,
                resources=self.resources,
                target_words=set(),
                answer="Answer 1",
            )
        with session_manager(self.db_manager):
            self.db_manager.add_task(
                template_id=self.template2_id,
                resources=self.four_choice_resources,
                target_words=set(),
                answer="A",
            )
        with session_manager(self.db_manager):
            self.db_manager.add_task(
                template_id=self.template2_id,
                resources=self.four_choice_resources,
                target_words=set(),
                answer="B",
            )

        # Fetch tasks by the first template
        tasks = self.db_manager.get_tasks_by_template(self.template2_id)
        self.assertEqual(len(tasks), 2)  # Two tasks should be from the first template

    def test_get_tasks_by_template_no_tasks(self):
        """
        Test the case when no tasks are returned.
        """
        another_template = TaskTemplate(
            starting_language=Language.ENGLISH,
            target_language=Language.GERMAN,
            template_description="Non-existent description",
            template_string="some string",
            template_examples=["Non-existent example 1"],
            parameter_description={"sentence": "Non-existent description."},
            task_type=TaskType.ONE_WAY_TRANSLATION,
        )
        with session_manager(self.db_manager):
            another_template_id = self.db_manager.add_template(another_template)
        tasks = self.db_manager.get_tasks_by_template(another_template_id)
        self.assertEqual(len(tasks), 0)  # No tasks should be returned

    def test_get_tasks_for_words(self):
        """
        Test retrieving tasks whose target words include all specified words.
        """
        target_words_subset = {self.word_1}  # This should match tasks with word_1
        with session_manager(self.db_manager):
            self.db_manager.add_task(
                template_id=self.template_id,
                resources=self.resources,
                target_words={self.word_1},
                answer="Extended",
            )

        with session_manager(self.db_manager):
            additional_word_id = self.db_manager.add_words_to_db(
                [("additional", "noun", 10)]
            )[0]
        additional_word = self.db_manager.get_word_by_id(additional_word_id)
        with session_manager(self.db_manager):
            self.db_manager.add_task(
                template_id=self.template_id,
                resources=self.resources,
                target_words={self.word_1, additional_word},
                answer="Extended",
            )

        # Test retrieving tasks that must include 'word_1'
        tasks = self.db_manager.get_tasks_for_words(target_words_subset)
        self.assertTrue(all(self.word_1 in task.learning_items for task in tasks))
        self.assertGreaterEqual(len(tasks), 2)  # Should find at least one task

    def test_get_tasks_for_words_no_match(self):
        """
        Test retrieving tasks where no tasks contain the specified target words.
        """
        with session_manager(self.db_manager):
            word_id = self.db_manager.add_words_to_db([("additional", "noun", 10)])[0]
        word = self.db_manager.get_word_by_id(word_id)
        tasks = self.db_manager.get_tasks_for_words({word})
        self.assertEqual(len(tasks), 0)  # No tasks should match

    def test_get_tasks_for_words_two_words(self):
        """
        Test retrieving tasks where there are two target words
        """
        two_words_ids = {self.word_1, self.word_2}
        with session_manager(self.db_manager):
            self.db_manager.add_task(
                template_id=self.template_id,
                resources=self.resources,
                target_words=two_words_ids,
                answer="Exact Match",
            )

        tasks = self.db_manager.get_tasks_for_words(two_words_ids)
        self.assertTrue(all(two_words_ids == task.learning_items for task in tasks))
        self.assertGreaterEqual(len(tasks), 1)  # At least one exact match should exist

    def test_get_tasks_for_words_superset(self):
        """
        Test retrieving tasks where the task has only one word out of two required
        """
        two_words = {self.word_1, self.word_2}
        with session_manager(self.db_manager):
            self.db_manager.add_task(
                template_id=self.template_id,
                resources=self.resources,
                target_words={self.word_1},
                answer="Superset Match",
            )

        tasks = self.db_manager.get_tasks_for_words(two_words)
        self.assertGreaterEqual(
            len(tasks), 0
        )  # Should find at least one superset match

    def create_example_task(self, resource_string1, resource_string2):
        answer = "Sample answer"
        resource1 = self.db_manager.add_resource_manual(resource_string1, {self.word_1})
        resource2 = self.db_manager.add_resource_manual(resource_string2, {self.word_1})
        resources = {"sentence": resource1, "phrase": resource2}
        task = self.db_manager.add_task(
            self.template.id, resources, {self.word_1}, answer
        )
        return task

    def test_remove_task_no_lessons(self):
        # add two tasks
        task1 = self.db_manager.add_task(
            template_id=self.template_id,
            resources=self.resources,
            target_words={self.word_1},
            answer="Extended",
        )
        task2 = self.db_manager.add_task(
            template_id=self.template_id,
            resources=self.resources,
            target_words={self.word_1, self.word_2},
            answer="Extended",
        )

        with self.db_manager.Session() as session:
            num_of_tasks = len(session.scalars(select(TaskDBObj)).all())
            self.assertEqual(num_of_tasks, 2)

            # remove one
            self.db_manager.remove_task(task2.id)

            # check
            num_of_tasks = len(session.scalars(select(TaskDBObj)).all())
            self.assertEqual(num_of_tasks, 1)
            
            with self.assertRaises(ValueDoesNotExistInDB):
                retrieved_task = self.db_manager.get_task_by_id(task2.id)
            # Ensure that no target words or resources are linked to the deleted task
            remaining_task_target_words = session.scalars(
                select(TaskTargetWordDBObj).where(
                    TaskTargetWordDBObj.task_id == task2.id
                )
            ).all()
            self.assertEqual(
                len(remaining_task_target_words),
                0,
                "No target words should remain for the deleted task",
            )

            remaining_task_resources = session.scalars(
                select(TaskResourceDBObj).where(TaskResourceDBObj.task_id == task2.id)
            ).all()
            self.assertEqual(
                len(remaining_task_resources),
                0,
                "No resources should remain for the deleted task",
            )

            retrieved_task = self.db_manager.get_task_by_id(task1.id)

            # Check that the retrieved task matches the added task
            self.assertEqual(retrieved_task.id, task1.id)
            self.assertEqual(retrieved_task.template.id, task1.template.id)
            self.assertEqual(retrieved_task.correctAnswer, task1.correctAnswer)

            # Check the resources and target words are correctly associated
            self.assertEqual(
                set(retrieved_task.resources.keys()), set(self.resources.keys())
            )
            self.assertEqual(
                set(lexical_item.id for lexical_item in retrieved_task.learning_items),
                set(word.id for word in task1.learning_items),
            )

    def test_remove_task_lessons(self):
        task1 = self.create_example_task("task1-r1", "task1-r2")
        task2 = self.create_example_task("task2-r1", "task2-r2")
        task3 = self.create_example_task("task3-r1", "task3-r2")

        evaluation1 = Evaluation()
        evaluation1.add_entry(task1, "response1", {Score(1, 4)})
        evaluation1.add_entry(task2, "response2", {Score(1, 6)})
        evaluation2 = Evaluation()
        evaluation2.add_entry(task3, "response3", {Score(1, 5), Score(2, 7)})

        lesson_data = [evaluation1, evaluation2]

        self.db_manager.save_user_lesson_data(self.user_id, lesson_data)

        with self.assertRaises(InvalidDelete):
            self.db_manager.remove_task(task1.id)


class TestUserLessonData(TestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        # add template
        # Create a template with two parameters
        with session_manager(self.db_manager):
            self.template_id = add_template(self.db_manager)
        word_1 = self.db_manager.get_word_by_id(1)
        word_2 = self.db_manager.get_word_by_id(2)
        self.select_words = {word_1, word_2}

    def tearDown(self):
        # Close the database connection and remove the test database file
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)

    def test_add_user_lesson_data(self):
        with session_manager(self.db_manager):
            lesson_data = create_example_lesson(self.db_manager, self.select_words, self.template_id)
        with session_manager(self.db_manager):
            self.db_manager.save_user_lesson_data(self.user_id, lesson_data)

        # Validate the insertion of user lesson data
        # Check user_lessons
        previous_lesson_data = self.db_manager.get_most_recent_lesson_data(self.user_id)
        if not previous_lesson_data:
            self.fail()

        with self.db_manager.Session() as session:
            lesson_number = len(
                session.scalars(
                    select(UserLessonDBObj).where(UserLessonDBObj.id == self.user_id)
                ).all()
            )
            self.assertEqual(lesson_number, 1)

        # Check evaluations
        self.assertEqual(len(previous_lesson_data), len(lesson_data))

        for retrieved_eval, evaluation in zip(previous_lesson_data, lesson_data):
            self.assertEqual(len(retrieved_eval.history), len(evaluation.history))

            for retr_history, history in zip(
                retrieved_eval.history, evaluation.history
            ):
                self.assertEqual(retr_history.response, history.response)
                self.assertEqual(retr_history.correction, history.correction)
                self.assertEqual(
                    retr_history.evaluation_result, history.evaluation_result
                )
                self.assertEqual(retr_history.task.id, history.task.id)

class TestRetrieveWordsForLesson(TestMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()

        with session_manager(self.db_manager):
            self.template_id = add_template(self.db_manager)
            # add first lesson
            self.word_1 = self.db_manager.get_word_by_id(self.word_ids[0])
            self.word_2 = self.db_manager.get_word_by_id(self.word_ids[2])

        with session_manager(self.db_manager):
            task = create_example_task(self.db_manager, "blah", "blah", {self.word_1, self.word_2}, self.template_id)
        with session_manager(self.db_manager):
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(self.word_1.id, 7)})
            evaluation1.add_entry(task, "response1", {Score(self.word_2.id, 8)})
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)
        with session_manager(self.db_manager):
            # Assume 'apple' and 'happy' get scores for the user
            self.db_manager.add_word_score(self.user_id, Score(self.word_ids[0], 7), lesson_id) # apple 
            self.db_manager.add_word_score(self.user_id, Score(self.word_ids[2], 8), lesson_id) # happy
            self.db_manager.shutdown_session() # NOTE session need to be shutdown to detect any uncommitted transactions

    def test_successful_retrieval(self):
        retrieved_words = self.db_manager.retrieve_words_for_lesson(self.user_id, 2)
        # Should retrieve 'run' and 'blue' as they are the highest frequency eligible words
        expected_words = {LexicalItem("run", "VERB", 60, 4), LexicalItem("blue", "ADJ", 20, 5)}
        self.assertEqual(retrieved_words, expected_words)

    def test_nonexistent_user(self):
        with self.assertRaises(ValueDoesNotExistInDB):
            self.db_manager.retrieve_words_for_lesson(9999, 2)  # Assuming 9999 does not exist

    def test_empty_result_set(self):        
        with session_manager(self.db_manager):
            task = create_example_task(self.db_manager, "blah", "blah", {self.word_1}, self.template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(self.word_1.id, 7)})
            lesson = [evaluation1]
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)
        with session_manager(self.db_manager):
            # User scored on all words
            for word_id in self.word_ids:
                self.db_manager.add_word_score(self.user_id, Score(word_id, 5), lesson_id)

        retrieved_words = self.db_manager.retrieve_words_for_lesson(self.user_id, 2)
        self.assertEqual(len(retrieved_words), 0)

    def test_partial_word_retrieval_due_to_scores(self):
        with session_manager(self.db_manager):
            task = create_example_task(self.db_manager, "blah", "blah", {self.word_1}, self.template_id)
            evaluation1 = Evaluation()
            evaluation1.add_entry(task, "response1", {Score(self.word_1.id, 7)})
            lesson = [evaluation1]
        with session_manager(self.db_manager):
            lesson_id = self.db_manager.save_user_lesson_data(self.user_id, lesson)
            # Adding additional words
            additional_words = [
                ("tree", "NOUN", 45), ("bright", "ADJ", 35), ("write", "VERB", 25)
            ]
        with session_manager(self.db_manager):
            additional_word_ids = self.db_manager.add_words_to_db(additional_words)
            # Assume 'tree' and 'bright' get scores for the user
            self.db_manager.add_word_score(self.user_id, Score(additional_word_ids[0], 6), lesson_id) # tree 
            self.db_manager.add_word_score(self.user_id, Score(additional_word_ids[1], 9), lesson_id) # bright

        # The user now has scores for 'apple', 'happy', 'tree', and 'bright'.
        # Remaining without scores are 'quickly', 'run', 'blue', 'write'.
        # Requesting 4 words, but only 3 are eligible (quickly is an adv).
        retrieved_words = self.db_manager.retrieve_words_for_lesson(self.user_id, 4)
        
        expected_words = {
            LexicalItem("run", "VERB", 60, 4),
            LexicalItem("blue", "ADJ", 20, 5),
            LexicalItem("write", "VERB", 25, 8)
        }
        self.assertEqual(set(retrieved_words), expected_words)
        self.assertEqual(len(retrieved_words), 3)  # Only three words should be returned


"""
HELPER FUNCTIONS
"""

def add_template(db_manager: DatabaseManager) -> int:
        """
        Adds an example template to the database and return its id.
        """
        template_string = (
        "Translate the following into English:\n" + "   '$sentence' and '$phrase'"
        )
        template_description = "Description of the template"
        template_examples = ["Example one", "Example two"]
        parameter_description = {
            "sentence": "Sentence in target language to be translated into English.",
            "phrase": "Phrase in target language to be translated into English.",
        }
        test_template = TaskTemplate(
            target_language=Language.GERMAN,
            starting_language=Language.ENGLISH,
            template_string=template_string,
            template_description=template_description,
            template_examples=template_examples,
            parameter_description=parameter_description,
            task_type=TaskType.ONE_WAY_TRANSLATION,
        )

        template_id = db_manager.add_template(test_template)
        return template_id

def create_example_task(
        db_manager: DatabaseManager, 
        resource_string1: str, 
        resource_string2: str,
        select_words: Set[LexicalItem],
        template_id: int    
    ) -> Task:
    answer = "Sample answer"
    resource1 = db_manager.add_resource_manual(resource_string1, select_words)
    resource2 = db_manager.add_resource_manual(resource_string2, select_words)
    resources = {"sentence": resource1, "phrase": resource2}
    task = db_manager.add_task(
        template_id, resources, select_words, answer
    )
    return task

def create_example_lesson(db_manager: DatabaseManager, select_words: Set[LexicalItem], template_id: int):
        task1 = create_example_task(db_manager, "task1-r1", "task1-r2", select_words, template_id)
        task2 = create_example_task(db_manager, "task2-r1", "task2-r2", select_words, template_id)
        task3 = create_example_task(db_manager, "task3-r1", "task3-r2", select_words, template_id)

        evaluation1 = Evaluation()
        evaluation1.add_entry(task1, "response1", {Score(1, 4)})
        evaluation1.add_entry(task2, "response2", {Score(1, 6)})
        evaluation2 = Evaluation()
        evaluation2.add_entry(task3, "response3", {Score(1, 5), Score(2, 7)})

        lesson_data = [evaluation1, evaluation2]
        return lesson_data