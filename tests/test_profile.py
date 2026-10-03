import os
import tempfile
import unittest
from app import create_app
from database.db import get_db, init_db
from models.user import UserModel
from models.profile import ProfileModel

class ProfileTestCase(unittest.TestCase):
    def setUp(self):
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
            # Create two test users
            self.user1_id = UserModel.create_user('alice', 'alice@test.com', 'password123')
            self.user2_id = UserModel.create_user('bob', 'bob@test.com', 'password123')

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def login(self, username, password):
        return self.client.post('/auth/login', data={
            'identifier': username,
            'password': password
        }, follow_redirects=True)

    def test_unauthenticated_profile_access(self):
        """Unauthenticated requests must redirect to login."""
        res = self.client.get('/profile/', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/auth/login', res.headers['Location'])

        res = self.client.get('/profile/edit', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/auth/login', res.headers['Location'])

    def test_edit_and_view_profile(self):
        """Test profile creation, update, and display."""
        self.login('alice', 'password123')

        # Edit profile POST
        res = self.client.post('/profile/edit', data={
            'full_name': 'Alice Smith',
            'date_of_birth': '1995-04-12',
            'blood_group': 'O+',
            'allergies': 'Penicillin, Peanuts',
            'current_medications': 'Cetirizine 10mg',
            'existing_conditions': 'Mild Seasonal Asthma',
            'previous_surgeries': 'None',
            'emergency_contact_name': 'Bob Smith (Spouse)',
            'emergency_contact_phone': '+1-555-0199'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Medical profile updated successfully', res.data)
        self.assertIn(b'Alice Smith', res.data)
        self.assertIn(b'O+', res.data)
        self.assertIn(b'Penicillin', res.data)
        self.assertIn(b'Bob Smith', res.data)

        # Verify directly in SQLite
        with self.app.app_context():
            profile = ProfileModel.get_by_user_id(self.user1_id)
            self.assertEqual(profile['full_name'], 'Alice Smith')
            self.assertEqual(profile['blood_group'], 'O+')
            self.assertEqual(profile['allergies'], 'Penicillin, Peanuts')

    def test_user_data_isolation(self):
        """Ensure User 1's profile is not mixed with User 2's profile."""
        with self.app.app_context():
            ProfileModel.update_profile(self.user1_id, {
                'full_name': 'Alice Smith',
                'blood_group': 'A+'
            })
            ProfileModel.update_profile(self.user2_id, {
                'full_name': 'Bob Jones',
                'blood_group': 'B-'
            })

        # Login as user 2 and verify only Bob's data shows
        self.login('bob', 'password123')
        res = self.client.get('/profile/')
        self.assertIn(b'Bob Jones', res.data)
        self.assertIn(b'B-', res.data)
        self.assertNotIn(b'Alice Smith', res.data)

if __name__ == '__main__':
    unittest.main()
