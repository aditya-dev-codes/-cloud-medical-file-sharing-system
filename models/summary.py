from database.db import get_db

class SummaryModel:
    """Helper functions for AI-generated medical summary records."""

    @staticmethod
    def create_or_update(report_id, summary_text, conditions, allergies, medications, is_mock=False):
        """Insert or replace an AI summary for a given report ID."""
        db = get_db()
        existing = db.execute(
            "SELECT id FROM ai_summaries WHERE report_id = ?",
            (report_id,)
        ).fetchone()

        if existing:
            db.execute("""
                UPDATE ai_summaries
                SET summary_text = ?,
                    extracted_conditions = ?,
                    extracted_allergies = ?,
                    extracted_medications = ?,
                    is_mock = ?,
                    created_at = CURRENT_TIMESTAMP
                WHERE report_id = ?
            """, (summary_text, conditions, allergies, medications, 1 if is_mock else 0, report_id))
        else:
            db.execute("""
                INSERT INTO ai_summaries (
                    report_id, summary_text, extracted_conditions,
                    extracted_allergies, extracted_medications, is_mock
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (report_id, summary_text, conditions, allergies, medications, 1 if is_mock else 0))

        db.commit()
        return True

    @staticmethod
    def get_by_report_id(report_id):
        """Fetch AI summary record for a specific report."""
        db = get_db()
        return db.execute(
            "SELECT * FROM ai_summaries WHERE report_id = ?",
            (report_id,)
        ).fetchone()

    @staticmethod
    def delete_by_report_id(report_id):
        """Delete AI summary for a report."""
        db = get_db()
        db.execute("DELETE FROM ai_summaries WHERE report_id = ?", (report_id,))
        db.commit()
