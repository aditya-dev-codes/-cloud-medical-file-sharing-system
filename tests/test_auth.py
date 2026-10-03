import os
import tempfile
import unittest
from app import create_app
from database.db import get_db, init_db
from models.user import UserModel

class AuthTestCase(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for SQLite database testing
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        
        class TestConfig:
            TESTING = True
            SECRET_KEY = 'test-secret-key'
            DATABASE = self.db_path
            UPLOAD_FOLDER = tempfile.mkdtemp()
            MAX_CONTENT_LENGTH = 16 * 1024 * 1024
            ALLOWED_EXTENSIONS = {'pdf', 'txt'}
            GEMINI_API_KEY = ''
            AI_MOCK_MODE = True

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            init_db(self.app)

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_database_tables_exist(self):
        """Verify all required tables exist in database."""
        with self.app.app_context():
            db = get_db()
            tables = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t['name'] for t in tables]
            for required in ['users', 'medical_profiles', 'medical_reports', 'ai_summaries']:
                self.assertIn(required, table_names)

    def test_user_registration_and_password_hashing(self):
        """Verify user is created with hashed password and medical_profile row initialized."""
        with self.app.app_context():
            user_id = UserModel.create_user('alice', 'alice@example.com', 'password123')
            self.assertIsNotNone(user_id)
            user = UserModel.get_by_id(user_id)
            self.assertEqual(user['username'], 'alice')
            self.assertNotEqual(user['password_hash'], 'password123')
            self.assertTrue(UserModel.verify_password(user['password_hash'], 'password123'))
            self.assertFalse(UserModel.verify_password(user['password_hash'], 'wrongpassword'))

    def test_auth_routes(self):
        """Test registration, login, logout, and protected route access."""
        # Unauthenticated access to dashboard should redirect to login
        res = self.client.get('/', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/auth/login', res.headers['Location'])

        # Register through HTTP POST
        res = self.client.post('/auth/register', data={
            'username': 'bob',
            'email': 'bob@example.com',
            'password': 'secretpassword',
            'confirm_password': 'secretpassword'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Registration successful', res.data)

        # Login with correct credentials
        res = self.client.post('/auth/login', data={
            'identifier': 'bob',
            'password': 'secretpassword'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Welcome', res.data)

        # Logout
        res = self.client.get('/auth/logout', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'successfully logged out', res.data)

        # Dashboard should again redirect
        res = self.client.get('/', follow_redirects=False)
        self.assertEqual(res.status_code, 302)

if __name__ == '__main__':
    unittest.main()
