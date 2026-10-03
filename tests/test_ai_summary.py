import os
import io
import shutil
import tempfile
import unittest
from app import create_app
from database.db import get_db, init_db
from models.user import UserModel
from models.report import ReportModel
from models.summary import SummaryModel
from services.text_extractor import TextExtractor
from services.ai_service import MockAIService, get_ai_service

class AISummaryTestCase(unittest.TestCase):
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

    def test_text_extractor_txt_and_pdf(self):
        """Test text extraction from both TXT and PDF files."""
        # 1. TXT
        txt_path = os.path.join(self.upload_dir, "test.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Clinical notes for testing extraction.")
        txt_res = TextExtractor.extract_text(txt_path, "TXT")
        self.assertIn("Clinical notes", txt_res)

        # 2. PDF (from prepared sample)
        pdf_path = os.path.join(os.path.dirname(__file__), "..", "samples", "sample_lab_report.pdf")
        if os.path.exists(pdf_path):
            pdf_res = TextExtractor.extract_text(pdf_path, "PDF")
            self.assertIn("METROPOLITAN HOSPITAL", pdf_res)
            self.assertIn("Penicillin", pdf_res)

    def test_mock_ai_service_summarization(self):
        """Test rule-based Mock AI summarizer accurately extracts key clinical facts."""
        sample_text = """
        Patient Diagnosis: Type 2 Diabetes Mellitus, Essential Hypertension.
        Known Allergies: Penicillin (severe), Peanuts.
        Current Medications: Metformin 500mg BID, Lisinopril 10mg QD.
        Previous Surgeries: Appendectomy 2020.
        Test Results: Fasting Blood Glucose 138 mg/dL.
        """
        service = MockAIService()
        result = service.summarize(sample_text, "lab_report.txt")

        self.assertTrue(result['is_mock'])
        self.assertIn("Type 2 Diabetes", result['extracted_conditions'])
        self.assertIn("Penicillin", result['extracted_allergies'])
        self.assertIn("Metformin", result['extracted_medications'])
        self.assertIn("CLINICAL SUMMARY FOR: lab_report.txt", result['summary_text'])

    def test_ai_summarization_route_and_persistence(self):
        """Test end-to-end report upload, summarization trigger, and DB persistence."""
        self.login('alice', 'password123')

        # 1. Upload report
        content = b"Diagnosis: Chronic Asthma.\nAllergies: Sulfa drugs.\nMedications: Albuterol inhaler."
        upload_res = self.client.post('/reports/upload', data={
            'report_file': (io.BytesIO(content), "asthma_report.txt")
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(upload_res.status_code, 200)

        with self.app.app_context():
            reports = ReportModel.get_by_user_id(self.user1_id)
            self.assertEqual(len(reports), 1)
            report_id = reports[0]['id']

        # 2. Trigger AI summary POST
        sum_res = self.client.post(f'/reports/{report_id}/summarize', follow_redirects=True)
        self.assertEqual(sum_res.status_code, 200)
        self.assertIn(b'Clinical summary generated successfully', sum_res.data)
        self.assertIn(b'Chronic Asthma', sum_res.data)
        self.assertIn(b'Sulfa drugs', sum_res.data)
        self.assertIn(b'Albuterol inhaler', sum_res.data)

        # 3. Verify in database
        with self.app.app_context():
            summary = SummaryModel.get_by_report_id(report_id)
            self.assertIsNotNone(summary)
            self.assertIn("Asthma", summary['extracted_conditions'])
            self.assertIn("Sulfa drugs", summary['extracted_allergies'])

    def test_cross_user_summarize_protection(self):
        """Ensure User B cannot trigger summarization on User A's document."""
        self.login('alice', 'password123')
        self.client.post('/reports/upload', data={
            'report_file': (io.BytesIO(b"Diagnosis: Secret Condition"), "secret.txt")
        }, content_type='multipart/form-data', follow_redirects=True)

        with self.app.app_context():
            report_id = ReportModel.get_by_user_id(self.user1_id)[0]['id']

        # Switch to Bob
        self.client.get('/auth/logout', follow_redirects=True)
        self.login('bob', 'password123')

        # Bob attempts POST summarize on Alice's report
        res = self.client.post(f'/reports/{report_id}/summarize', follow_redirects=True)
        self.assertIn(b'access denied', res.data)

        # Verify no summary was saved
        with self.app.app_context():
            self.assertIsNone(SummaryModel.get_by_report_id(report_id))

    def test_gemini_service_fallback_on_invalid_key(self):
        """Ensure GeminiAIService falls back seamlessly to Mock mode on API/network errors."""
        from services.ai_service import GeminiAIService
        service = GeminiAIService(api_key="invalid_mock_key_999")
        sample_doc = "Diagnosis: Acute Bronchitis.\nAllergies: Penicillin.\nMedications: Amoxicillin."
        
        result = service.summarize(sample_doc, "bronchitis.txt")
        # Should gracefully fall back without throwing an unhandled exception
        self.assertTrue(result['is_mock'])
        self.assertIn("Switched to Local Mock Summarizer", result['summary_text'])
        self.assertIn("Penicillin", result['extracted_allergies'])

    def test_gemini_service_successful_parsing(self):
        """Test GeminiAIService parsing when valid JSON response is received."""
        import json
        from unittest.mock import patch, MagicMock
        from services.ai_service import GeminiAIService

        mock_gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '```json\n{\n  "summary_text": "Patient has stable Type 2 Diabetes.",\n  "extracted_conditions": "Type 2 Diabetes",\n  "extracted_allergies": "No known drug allergies",\n  "extracted_medications": "Metformin 500mg"\n}\n```'
                            }
                        ]
                    }
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_gemini_response).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp

        with patch('urllib.request.urlopen', return_value=mock_resp):
            service = GeminiAIService(api_key="valid_test_key")
            result = service.summarize("Patient has Type 2 Diabetes.", "report.txt")
            self.assertFalse(result['is_mock'])
            self.assertEqual(result['summary_text'], "Patient has stable Type 2 Diabetes.")
            self.assertEqual(result['extracted_conditions'], "Type 2 Diabetes")
            self.assertEqual(result['extracted_medications'], "Metformin 500mg")

if __name__ == '__main__':
    unittest.main()
