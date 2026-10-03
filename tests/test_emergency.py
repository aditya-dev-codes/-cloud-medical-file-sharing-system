import os
import io
import shutil
import tempfile
import unittest
from app import create_app
from database.db import get_db, init_db
from models.user import UserModel
from models.profile import ProfileModel
from models.report import ReportModel
from models.summary import SummaryModel

class EmergencyTestCase(unittest.TestCase):
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
                'previous_surgeries': 'Appendectomy 2020',
                'emergency_contact_name': 'John Smith',
                'emergency_contact_phone': '+1-555-9999'
            })

            # Create a report and AI summary for Alice
            report_id = ReportModel.create(
                user_id=self.user1_id,
                filename="alice_lab.txt",
                original_filename="alice_lab.txt",
                file_path="1/alice_lab.txt",
                file_size=1024,
                file_type="TXT"
            )
            SummaryModel.create_or_update(
                report_id=report_id,
                summary_text="CLINICAL SUMMARY: Glucose elevated. Penicillin allergy confirmed.",
                conditions="Type 2 Diabetes",
                allergies="Penicillin",
                medications="Metformin",
                is_mock=True
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

    def test_unauthenticated_emergency_access(self):
        """Unauthenticated requests must redirect to login."""
        for ep in ['/emergency/', '/emergency/view']:
            res = self.client.get(ep, follow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/auth/login', res.headers['Location'])

    def test_emergency_hub_and_view(self):
        """Test authenticated access to emergency hub and consolidated emergency card view."""
        self.login('alice', 'password123')

        # Emergency Hub
        res_hub = self.client.get('/emergency/')
        self.assertEqual(res_hub.status_code, 200)
        self.assertIn(b'Emergency Share Hub', res_hub.data)
        self.assertIn(b'O+', res_hub.data)

        # Emergency View
        res_view = self.client.get('/emergency/view')
        self.assertEqual(res_view.status_code, 200)
        self.assertIn(b'EMERGENCY MEDICAL PROFILE', res_view.data)
        self.assertIn(b'Alice Smith', res_view.data)
        self.assertIn(b'O+', res_view.data)
        self.assertIn(b'Penicillin Anaphylaxis', res_view.data)
        self.assertIn(b'John Smith', res_view.data)
        self.assertIn(b'+1-555-9999', res_view.data)
        self.assertIn(b'Glucose elevated', res_view.data)
        self.assertIn(b'alice_lab.txt', res_view.data)

    def test_cross_user_isolation_emergency(self):
        """Ensure Bob does not see Alice's emergency profile data."""
        self.login('bob', 'password123')

        res = self.client.get('/emergency/view')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b'Alice Smith', res.data)
        self.assertNotIn(b'Penicillin Anaphylaxis', res.data)
        self.assertNotIn(b'alice_lab.txt', res.data)

if __name__ == '__main__':
    unittest.main()
