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

class Milestone7WorkflowTestCase(unittest.TestCase):
    """
    Comprehensive verification of Milestone 7 requirements:
    1. SHA-256 Token Hashing (tokens not stored in plaintext)
    2. Expiration and Revocation handling
    3. Emergency Report Permission Filtering (allow vs exclude)
    4. Emergency Doctor Public Profile Viewer (read-only, no auth required)
    5. Blocked direct access to private documents
    6. Complete Access Audit Logging
    """

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.upload_dir = tempfile.mkdtemp()

        class TestConfig:
            TESTING = True
            SECRET_KEY = 'test-secret-key-m7'
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

            # Populate Alice's medical profile
            ProfileModel.update_profile(self.user1_id, {
                'full_name': 'Alice Smith',
                'date_of_birth': '1995-04-12',
                'blood_group': 'O+',
                'allergies': 'Penicillin Anaphylaxis',
                'current_medications': 'Metformin 500mg daily',
                'existing_conditions': 'Type 2 Diabetes',
                'previous_surgeries': 'Appendectomy (2018)',
                'emergency_contact_name': 'John Smith',
                'emergency_contact_phone': '+1-555-0199'
            })

            # Create Report 1 (Emergency Allowed = 1)
            user1_folder = os.path.join(self.upload_dir, str(self.user1_id))
            os.makedirs(user1_folder, exist_ok=True)
            report1_path = os.path.join(user1_folder, "public_lab.txt")
            with open(report1_path, "w", encoding="utf-8") as f:
                f.write("Public Lab Report: Blood Glucose 110 mg/dL.")

            self.report1_id = ReportModel.create(
                user_id=self.user1_id,
                filename="public_lab.txt",
                original_filename="public_lab.txt",
                file_path=f"{self.user1_id}/public_lab.txt",
                file_size=len("Public Lab Report: Blood Glucose 110 mg/dL."),
                file_type="TXT",
                emergency_access_allowed=1
            )

            # Create Report 2 (Emergency Excluded = 0, Private)
            report2_path = os.path.join(user1_folder, "confidential_notes.txt")
            with open(report2_path, "w", encoding="utf-8") as f:
                f.write("Confidential therapy session notes.")

            self.report2_id = ReportModel.create(
                user_id=self.user1_id,
                filename="confidential_notes.txt",
                original_filename="confidential_notes.txt",
                file_path=f"{self.user1_id}/confidential_notes.txt",
                file_size=len("Confidential therapy session notes."),
                file_type="TXT",
                emergency_access_allowed=0
            )

            # Add AI summary for permitted Report 1
            SummaryModel.create_or_update(
                report_id=self.report1_id,
                summary_text="Factual extract: Blood Glucose level 110 mg/dL.",
                conditions="Diabetes",
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

    def test_token_hash_stored_not_raw(self):
        """Verify tokens are hashed with SHA-256 and raw token is NEVER in database."""
        with self.app.app_context():
            raw_token, token_rec = TokenModel.create(self.user1_id, duration_hours=24, label="Audit Test")
            
            # Check SQLite row directly
            db = get_db()
            row = db.execute("SELECT * FROM emergency_tokens WHERE id = ?", (token_rec['id'],)).fetchone()
            
            # Ensure raw_token is not stored in plaintext in the table
            self.assertNotEqual(row['token_hash'], raw_token)
            self.assertEqual(row['token_hash'], TokenModel.hash_token(raw_token))
            self.assertEqual(row['token_prefix'], raw_token[:8])
            self.assertEqual(row['is_active'], 1)
            self.assertEqual(row['access_count'], 0)

    def test_token_validation_and_access_increment(self):
        """Verify token validation increments access_count and updates last_accessed_at."""
        with self.app.app_context():
            raw_token, token_rec = TokenModel.create(self.user1_id, duration_hours=6)
            self.assertEqual(token_rec['access_count'], 0)

            # Validate first time
            tok1, status1 = TokenModel.validate_token(raw_token)
            self.assertEqual(status1, 'VALID')
            self.assertEqual(tok1['access_count'], 1)
            self.assertIsNotNone(tok1['last_accessed_at'])

            # Validate second time
            tok2, status2 = TokenModel.validate_token(raw_token)
            self.assertEqual(status2, 'VALID')
            self.assertEqual(tok2['access_count'], 2)

    def test_token_expiry_and_revocation(self):
        """Verify expired or revoked tokens return correct status."""
        with self.app.app_context():
            # Expired token
            raw_exp, rec_exp = TokenModel.create(self.user1_id, duration_hours=-2)
            tok_exp, status_exp = TokenModel.validate_token(raw_exp)
            self.assertEqual(status_exp, 'EXPIRED')

            # Revoked token
            raw_act, rec_act = TokenModel.create(self.user1_id, duration_hours=24)
            TokenModel.revoke(rec_act['id'], self.user1_id)
            tok_rev, status_rev = TokenModel.validate_token(raw_act)
            self.assertEqual(status_rev, 'REVOKED')

    def test_emergency_report_permission_filtering(self):
        """Verify doctor sees permitted reports and AI summaries, but excluded report is completely hidden."""
        with self.app.app_context():
            raw_token, _ = TokenModel.create(self.user1_id, duration_hours=24)

        res = self.client.get(f'/emergency/{raw_token}')
        self.assertEqual(res.status_code, 200)

        # Permitted report should be visible
        self.assertIn(b'public_lab.txt', res.data)
        self.assertIn(b'Factual extract: Blood Glucose level 110 mg/dL.', res.data)

        # Excluded report must NOT be visible
        self.assertNotIn(b'confidential_notes.txt', res.data)

    def test_emergency_doctor_cannot_download_excluded_report(self):
        """Verify requesting excluded report returns HTTP 403 Forbidden even with valid token."""
        with self.app.app_context():
            raw_token, _ = TokenModel.create(self.user1_id, duration_hours=24)

        # Attempt to download permitted report -> 200 OK
        res1 = self.client.get(f'/emergency/{raw_token}/report/{self.report1_id}')
        self.assertEqual(res1.status_code, 200)
        self.assertIn(b'Public Lab Report', res1.data)
        res1.close()

        # Attempt to download private/excluded report -> 403 Forbidden
        res2 = self.client.get(f'/emergency/{raw_token}/report/{self.report2_id}')
        self.assertEqual(res2.status_code, 403)

    def test_patient_can_toggle_report_emergency_permission(self):
        """Verify patient can toggle report permission from private to permitted and back."""
        self.login('alice', 'password123')

        # Toggle Report 2 from 0 to 1
        res = self.client.post(f'/reports/{self.report2_id}/toggle-emergency', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            rep = ReportModel.get_by_id(self.report2_id)
            self.assertEqual(rep['emergency_access_allowed'], 1)

        # Toggle back to 0
        res = self.client.post(f'/reports/{self.report2_id}/toggle-emergency', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            rep = ReportModel.get_by_id(self.report2_id)
            self.assertEqual(rep['emergency_access_allowed'], 0)

    def test_emergency_access_audit_logging(self):
        """Verify every profile view and document access is logged for patient auditing."""
        with self.app.app_context():
            raw_token, token_rec = TokenModel.create(self.user1_id, duration_hours=24)

        # Access profile
        self.client.get(f'/emergency/{raw_token}')
        # Access permitted document
        self.client.get(f'/emergency/{raw_token}/report/{self.report1_id}')

        with self.app.app_context():
            logs = AccessLogModel.get_by_user_id(self.user1_id)
            self.assertEqual(len(logs), 2)
            actions = [l['action'] for l in logs]
            self.assertIn('VIEW_PROFILE', actions)
            self.assertIn('DOWNLOAD_REPORT', actions)
            for l in logs:
                self.assertEqual(l['status'], 'SUCCESS')

if __name__ == '__main__':
    unittest.main()
