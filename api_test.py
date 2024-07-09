import unittest
from flask import Flask
from app_factory import create_app
from database_orm import DatabaseManager

class UserBlueprintTestCase(unittest.TestCase):
    def setUp(self):
        """Set up test variables and initialize app."""
        self.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        self.client = self.app.test_client()

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

        

if __name__ == '__main__':
    unittest.main()