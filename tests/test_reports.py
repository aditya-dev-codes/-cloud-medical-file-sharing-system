import os
import io
import shutil
import tempfile
import unittest
from app import create_app
from database.db import get_db, init_db
from models.user import UserModel
from models.report import ReportModel
from services.storage import LocalStorageService

class ReportsTestCase(unittest.TestCase):
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

    def test_unauthenticated_reports_access(self):
        """Unauthenticated requests must be redirected to login."""
        endpoints = ['/reports/', '/reports/upload', '/reports/1', '/reports/1/download']
        for ep in endpoints:
            res = self.client.get(ep, follow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/auth/login', res.headers['Location'])

    def test_upload_txt_report(self):
        """Test uploading a valid TXT medical report."""
        self.login('alice', 'password123')

        data = {
            'report_file': (io.BytesIO(b"Patient Diagnosis: Routine checkup normal. Blood pressure 120/80."), "routine_checkup.txt")
        }
        res = self.client.post('/reports/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'uploaded successfully', res.data)
        self.assertIn(b'routine_checkup.txt', res.data)

        # Verify in database
        with self.app.app_context():
            reports = ReportModel.get_by_user_id(self.user1_id)
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0]['original_filename'], 'routine_checkup.txt')
            self.assertEqual(reports[0]['file_type'], 'TXT')
            # Verify file exists on disk
            abs_path = LocalStorageService.get_absolute_path(reports[0]['file_path'])
            self.assertTrue(abs_path.exists())

    def test_upload_disallowed_file_type(self):
        """Test uploading a disallowed file type (e.g. .py or .exe) is rejected."""
        self.login('alice', 'password123')

        data = {
            'report_file': (io.BytesIO(b"print('hack')"), "malicious.py")
        }
        res = self.client.post('/reports/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Invalid file type', res.data)

        with self.app.app_context():
            reports = ReportModel.get_by_user_id(self.user1_id)
            self.assertEqual(len(reports), 0)

    def test_download_and_cross_user_isolation(self):
        """Verify user can download their report, but another user cannot."""
        # 1. Alice uploads a report
        self.login('alice', 'password123')
        data = {
            'report_file': (io.BytesIO(b"Alice Private Medical Notes: Confidential"), "alice_notes.txt")
        }
        self.client.post('/reports/upload', data=data, content_type='multipart/form-data', follow_redirects=True)

        with self.app.app_context():
            report = ReportModel.get_by_user_id(self.user1_id)[0]
            report_id = report['id']

        # Alice downloads -> 200 OK
        res = self.client.get(f'/reports/{report_id}/download')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Alice Private Medical Notes', res.data)
        res.close()

        # 2. Bob logs in and tries to access Alice's report
        self.client.get('/auth/logout', follow_redirects=True)
        self.login('bob', 'password123')

        # Bob views Alice's report -> redirect / error
        res = self.client.get(f'/reports/{report_id}', follow_redirects=True)
        self.assertIn(b'not authorized', res.data)

        # Bob downloads Alice's report -> 404 forbidden
        res = self.client.get(f'/reports/{report_id}/download')
        self.assertEqual(res.status_code, 404)

        # Bob tries to delete Alice's report -> not authorized
        res = self.client.post(f'/reports/{report_id}/delete', follow_redirects=True)
        self.assertIn(b'not authorized', res.data)

    def test_delete_report(self):
        """Verify report owner can delete the report from DB and disk."""
        self.login('alice', 'password123')
        data = {
            'report_file': (io.BytesIO(b"To be deleted"), "temp_report.txt")
        }
        self.client.post('/reports/upload', data=data, content_type='multipart/form-data', follow_redirects=True)

        with self.app.app_context():
            report = ReportModel.get_by_user_id(self.user1_id)[0]
            report_id = report['id']
            abs_path = LocalStorageService.get_absolute_path(report['file_path'])
            self.assertTrue(abs_path.exists())

        # Delete report
        res = self.client.post(f'/reports/{report_id}/delete', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'was deleted', res.data)

        # Verify disk and DB
        self.assertFalse(abs_path.exists())
        with self.app.app_context():
            self.assertIsNone(ReportModel.get_by_id(report_id))

if __name__ == '__main__':
    unittest.main()
