import os
import io
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from app import create_app
from database.db import get_db, init_db
from models.user import UserModel
from models.profile import ProfileModel
from models.report import ReportModel
from models.summary import SummaryModel
from models.token import TokenModel
from models.access_log import AccessLogModel

class EmergencyTokensTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.upload_dir = tempfile.mkdtemp()

        class TestConfig:
            TESTING = True
            SECRET_KEY = 'test-secret-key'
            DATABASE = self.db_path
            UPLOAD_FOLDER = self.upload_dir
            MAX_CONTENT_LENGTH = 16 * 1024 * 1024
            ALLOWED_EXTENSIONS = {'pdf', 'txt'}
            GEMINI_API_KEY = ''
            AI_MOCK_MODE = True

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            init_db(self.app)
            self.user1_id = UserModel.create_user('alice', 'alice@test.com', 'password123')
            self.user2_id = UserModel.create_user('bob', 'bob@test.com', 'password123')

            # Populate Alice's profile
            ProfileModel.update_profile(self.user1_id, {
                'full_name': 'Alice Smith',
                'date_of_birth': '1995-04-12',
                'blood_group': 'O+',
                'allergies': 'Penicillin Anaphylaxis',
                'current_medications': 'Metformin 500mg',
                'existing_conditions': 'Type 2 Diabetes',
                'emergency_contact_name': 'John Smith',
                'emergency_contact_phone': '+1-555-9999'
            })

            # Create sample report on disk for Alice
            user1_folder = os.path.join(self.upload_dir, str(self.user1_id))
            os.makedirs(user1_folder, exist_ok=True)
            report_file_path = os.path.join(user1_folder, "alice_notes.txt")
            with open(report_file_path, "w", encoding="utf-8") as f:
                f.write("Clinical notes for Alice: Blood glucose 138.")

            self.report1_id = ReportModel.create(
                user_id=self.user1_id,
                filename="alice_notes.txt",
                original_filename="alice_notes.txt",
                file_path=f"{self.user1_id}/alice_notes.txt",
                file_size=len("Clinical notes for Alice: Blood glucose 138."),
                file_type="TXT"
            )

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.upload_dir):
            shutil.rmtree(self.upload_dir, ignore_errors=True)

    def login(self, username, password):
        return self.client.post('/auth/login', data={
            'identifier': username,
            'password': password
        }, follow_redirects=True)

    def test_token_creation_and_lifecycle(self):
        """Test token creation, duration, expiration check, and revocation."""
        with self.app.app_context():
            token = TokenModel.create(self.user1_id, duration_hours=2, label="ER Link")
            self.assertIsNotNone(token)
            self.assertEqual(token['user_id'], self.user1_id)
            self.assertEqual(token['is_revoked'], 0)
            self.assertTrue(len(token['token']) >= 24)

            # Validate active token
            tok, status = TokenModel.validate_token(token['token'])
            self.assertEqual(status, 'VALID')

            # Test revocation
            TokenModel.revoke(token['id'], self.user1_id)
            tok, status = TokenModel.validate_token(token['token'])
            self.assertEqual(status, 'REVOKED')

            # Test invalid token
            tok, status = TokenModel.validate_token("non_existent_token_123")
            self.assertEqual(status, 'INVALID')

    def test_token_expiration(self):
        """Test that past expiration timestamps are correctly identified as EXPIRED."""
        with self.app.app_context():
            token = TokenModel.create(self.user1_id, duration_hours=-1, label="Expired Link")
            tok, status = TokenModel.validate_token(token['token'])
            self.assertEqual(status, 'EXPIRED')

    def test_public_emergency_access_route(self):
        """Test public emergency access endpoint with valid, revoked, and expired tokens."""
        with self.app.app_context():
            token_valid = TokenModel.create(self.user1_id, duration_hours=2, label="Valid ER Link")
            token_revoked = TokenModel.create(self.user1_id, duration_hours=2, label="Revoked Link")
            TokenModel.revoke(token_revoked['id'], self.user1_id)
            token_expired = TokenModel.create(self.user1_id, duration_hours=-2, label="Expired Link")

        # 1. Valid token -> 200 OK with clinical info
        res = self.client.get(f'/emergency/access/{token_valid["token"]}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'EMERGENCY MEDICAL PROFILE', res.data)
        self.assertIn(b'Alice Smith', res.data)
        self.assertIn(b'O+', res.data)
        self.assertIn(b'Penicillin Anaphylaxis', res.data)
        self.assertIn(b'+1-555-9999', res.data)
        # Verify normal user account controls are NOT exposed
        self.assertNotIn(b'Logout', res.data)
        self.assertNotIn(b'Edit Profile', res.data)

        # 2. Revoked token -> 403 Forbidden
        res = self.client.get(f'/emergency/access/{token_revoked["token"]}')
        self.assertEqual(res.status_code, 403)
        self.assertIn(b'Link Revoked', res.data)

        # 3. Expired token -> 403 Forbidden
        res = self.client.get(f'/emergency/access/{token_expired["token"]}')
        self.assertEqual(res.status_code, 403)
        self.assertIn(b'Link Expired', res.data)

        # 4. Non-existent token -> 404 Not Found
        res = self.client.get('/emergency/access/random_invalid_token')
        self.assertEqual(res.status_code, 404)
        self.assertIn(b'Invalid Emergency Link', res.data)

    def test_token_authorized_report_download(self):
        """Test emergency doctor downloading patient report with a valid token."""
        with self.app.app_context():
            token = TokenModel.create(self.user1_id, duration_hours=2, label="ER Download Link")

        # Download report via token
        res = self.client.get(f'/emergency/access/{token["token"]}/report/{self.report1_id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Clinical notes for Alice', res.data)
        res.close()

        # Revoke token and verify download is immediately blocked
        with self.app.app_context():
            TokenModel.revoke(token['id'], self.user1_id)

        res = self.client.get(f'/emergency/access/{token["token"]}/report/{self.report1_id}')
        self.assertEqual(res.status_code, 403)

    def test_emergency_access_logging(self):
        """Verify access attempts are recorded in access_logs table and viewable by patient."""
        with self.app.app_context():
            token = TokenModel.create(self.user1_id, duration_hours=2, label="Audit Test Link")

        # Trigger access
        self.client.get(f'/emergency/access/{token["token"]}')

        # Verify log entry in database
        with self.app.app_context():
            logs = AccessLogModel.get_by_user_id(self.user1_id)
            self.assertTrue(len(logs) >= 1)
            self.assertEqual(logs[0]['action'], 'VIEW_PROFILE')
            self.assertEqual(logs[0]['status'], 'SUCCESS')

        # Log in as Alice and view audit log on Emergency Hub
        self.login('alice', 'password123')
        res = self.client.get('/emergency/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Emergency Access Audit History', res.data)
        self.assertIn(b'View Profile', res.data)
        self.assertIn(b'Allowed', res.data)

if __name__ == '__main__':
    unittest.main()
