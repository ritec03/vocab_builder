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
        

if __name__ == '__main__':
    unittest.main()