from database.db import get_db

class ReportModel:
    """Helper functions for medical report metadata management."""

    @staticmethod
    def create(user_id, filename, original_filename, file_path, file_size, file_type):
        """Insert uploaded medical report metadata into SQLite."""
        db = get_db()
        cursor = db.execute("""
            INSERT INTO medical_reports (
                user_id, filename, original_filename, file_path, file_size, file_type
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, filename, original_filename, file_path, file_size, file_type))
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def get_by_id(report_id):
        """Fetch report metadata by report ID."""
        db = get_db()
        return db.execute(
            "SELECT * FROM medical_reports WHERE id = ?",
            (report_id,)
        ).fetchone()

    @staticmethod
    def get_user_report(report_id, user_id):
        """Fetch report ensuring it belongs to the authenticated user."""
        db = get_db()
        return db.execute(
            "SELECT * FROM medical_reports WHERE id = ? AND user_id = ?",
            (report_id, user_id)
        ).fetchone()

    @staticmethod
    def get_by_user_id(user_id):
        """Fetch all reports uploaded by a user ordered by newest first."""
        db = get_db()
        return db.execute(
            "SELECT * FROM medical_reports WHERE user_id = ? ORDER BY uploaded_at DESC",
            (user_id,)
        ).fetchall()

    @staticmethod
    def delete(report_id, user_id):
        """
        Delete report metadata from database.
        Returns the report record if deleted, or None if not found/unauthorized.
        """
        db = get_db()
        report = ReportModel.get_user_report(report_id, user_id)
        if not report:
            return None

        db.execute(
            "DELETE FROM medical_reports WHERE id = ? AND user_id = ?",
            (report_id, user_id)
        )
        db.commit()
        return report
