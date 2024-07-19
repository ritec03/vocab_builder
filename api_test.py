import json
from typing import List
import unittest
from flask import Flask
import pandas as pd
from sqlalchemy import Tuple
from app_factory import create_app
from data_structures import NUM_WORDS_PER_LESSON
from database_orm import DatabaseManager, read_tasks_from_json, read_templates_from_json
from exercise import SpacedRepetitionLessonGenerator

class UserBlueprintTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        templates = read_templates_from_json("templates.json")
        word_freq_output_file_path = "word_freq.txt"
        word_freq_df_loaded = pd.read_csv(word_freq_output_file_path, sep="\t")
        filtered_dataframe = word_freq_df_loaded[word_freq_df_loaded["count"] > 2]
        list_of_tuples: List[Tuple[str, str, int]] = list(filtered_dataframe.to_records(index=False))
        # convert numpy.int64 to Python integer
        cls.list_of_tuples = [(word, pos, int(freq)) for (word, pos, freq) in list_of_tuples][:100]

    def setUp(self):
        """Set up test variables and initialize app."""
        self.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        db_manager: DatabaseManager = self.app.db_manager
        self.client = self.app.test_client()
        db_manager.add_words_to_db(self.list_of_tuples)

    def test_create_user(self):
        """Test API can create a user (POST request)."""
        res = self.client.post('/users', json={'user_name': 'abc'})
        self.assertEqual(res.status_code, 201)
        self.assertIn('user_id', res.get_json())

    def test_create_duplicate_user(self):
        """Test API can create a user (POST request)."""
        res1 = self.client.post('/users', json={'user_name': 'abc'})
        db_manager: DatabaseManager = self.app.db_manager
        user = db_manager.get_user_by_id(1)
        self.assertEqual(user.id, 1)
        res2 = self.client.post('/users', json={'user_name': 'abc'})
        self.assertEqual(res2.status_code, 409)

    def test_get_user(self):
        """Test API can get a user (GET request)."""
        post_res = self.client.post('/users', json={'user_name': 'testuser'})
        user_id = post_res.get_json()['user_id']
        res = self.client.get(f'/users/{user_id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn('testuser', res.get_json()['user_name'])
    
    def test_non_existent_user(self):
        """Test API for non existent user getting"""
        res = self.client.get(f'/users/{999}')
        self.assertEqual(res.status_code, 404)

    def test_delete_user(self):
        """Test API can delete an existing user (DELETE request)."""
        post_res = self.client.post('/users', json={'user_name': 'testuser'})
        user_id = post_res.get_json()['user_id']
        res = self.client.delete(f'/users/{user_id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn('User deleted', res.get_json()['status'])

    def test_delete_nonexistent_user(self):
        """Test API can delete a non-existing user (DELETE request)."""
        res = self.client.delete(f'/users/{999}')
        self.assertEqual(res.status_code, 404)

    
    def test_delete_nonexistent_user(self):
        """Test API can delete a non-existing user (DELETE request)."""
        res = self.client.delete(f'/users/{999}')
        self.assertEqual(res.status_code, 404)


class LessonBlueprintTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        
        word_freq_output_file_path = "word_freq.txt"
        word_freq_df_loaded = pd.read_csv(word_freq_output_file_path, sep="\t")
        filtered_dataframe = word_freq_df_loaded[word_freq_df_loaded["count"] > 2]
        list_of_tuples: List[Tuple[str, str, int]] = list(filtered_dataframe.to_records(index=False))
        # convert numpy.int64 to Python integer
        cls.list_of_tuples = [(word, pos, int(freq)) for (word, pos, freq) in list_of_tuples][:100]

    def prepopulate_db(self, db_manager: DatabaseManager):
        # add template and create template dict
        templates = read_templates_from_json("templates.json")
        template_dict = dict()
        for template in templates:
            added_template_id = db_manager.add_template(template)
            template_dict[template.get_template_string()] = added_template_id
        db_manager.add_words_to_db(self.list_of_tuples)
        tasks = read_tasks_from_json("tasks.json")
        for task in tasks:
            task.template.id = template_dict[task.template.get_template_string()]
            for key in task.resources.keys():
                db_manager.add_resource_manual(task.resources[key].resource, task.resources[key].target_words)
            db_manager.add_task(task.template.id, task.resources, task.learning_items, task.correctAnswer)

    def setUp(self):
        """Set up test variables and initialize app."""
        self.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        db_manager: DatabaseManager = self.app.db_manager
        self.client = self.app.test_client()
        self.prepopulate_db(db_manager)
        res = self.client.post('/users', json={'user_name': 'abc'})
        self.user_id = res.get_json()["user_id"]

    def test_request_first_lesson(self):
        res = self.client.post(f'/users/{self.user_id}/lessons')
        self.assertEqual(res.status_code, 201)
        self.assertIn('lesson_id', res.get_json())
        self.assertIn('task', res.get_json())
        self.assertIn('order', res.get_json()["task"])
        self.assertIn('first_task', res.get_json()["task"])

    # TODO think about the random nature of the tests here.
    def test_submit_answer(self):
        res = self.client.post(f'/users/{self.user_id}/lessons')
        data = res.get_json()

        request_data = {
            "task_id": data["task"]["first_task"]["id"],
            "task_order": data["task"]["order"],
            "answer": "B"
        }

        # Simulate POST request with JSON data
        response = self.client.post(f'/users/{self.user_id}/lessons/{data["lesson_id"]}/tasks/submit',
                                    data=json.dumps(request_data),
                                    content_type='application/json')
        
        # Assert response status code
        self.assertEqual(response.status_code, 201)  # Assuming it returns 201 on success
        
        # Optionally, assert the response content
        response_data = json.loads(response.data)
        self.assertIn("score", response_data)
        self.assertIn("next_task", response_data)
        # TODO convert order to a list from tuple?
        self.assertEquals(response_data["next_task"]["order"], [data["task"]["order"][0]+1, data["task"]["order"][1]])

    def test_finish_lesson(self):
        # NOTE for this test for now set NUM_WORDS_PER_LESSON to 2 manually
        # request lesson and first task
        res = self.client.post(f'/users/{1}/lessons')
        data = res.get_json()
        self.assertEqual(res.status_code, 201)

        # submit the task 
        request_data = {
            "task_id": data["task"]["first_task"]["id"],
            "task_order": data["task"]["order"],
            "answer": "B"
        }

        response = self.client.post(f'/users/{1}/lessons/{data["lesson_id"]}/tasks/submit',
                                    data=json.dumps(request_data),
                                    content_type='application/json')
        response_data = json.loads(response.data)
        self.assertIn("score", response_data)
        self.assertIn("next_task", response_data)

        # submit the second task
        request_data = {
            "task_id": response_data["next_task"]["task"]["id"],
            "task_order": response_data["next_task"]["order"],
            "answer": "C"
        }

        response = self.client.post(f'/users/{1}/lessons/{data["lesson_id"]}/tasks/submit',
                                    data=json.dumps(request_data),
                                    content_type='application/json')
        response_data = json.loads(response.data)
        self.assertIn("score", response_data)
        self.assertIn("next_task", response_data)

        # check that there is no further task and that the structure of response is as expected
        self.assertIsNone(response_data["next_task"])
        self.assertIn("score", response_data)
        self.assertIn("final_scores", response_data)

        # request a new lesson and make sure the lesson id is not the same as before
        res = self.client.post(f'/users/{1}/lessons')
        new_data = res.get_json()
        self.assertNotEqual(new_data["lesson_id"], data["lesson_id"])

if __name__ == '__main__':
    unittest.main()