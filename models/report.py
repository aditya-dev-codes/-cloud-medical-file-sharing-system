from database.db import get_db

class ReportModel:
    """Helper functions for medical report metadata management and emergency permissions."""

    @staticmethod
    def create(user_id, filename, original_filename, file_path, file_size, file_type, emergency_access_allowed=1):
        """Insert uploaded medical report metadata into SQLite."""
        db = get_db()
        cursor = db.execute("""
            INSERT INTO medical_reports (
                user_id, filename, original_filename, file_path, file_size, file_type, emergency_access_allowed
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, filename, original_filename, file_path, file_size, file_type, 1 if emergency_access_allowed else 0))
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
    def get_emergency_reports(user_id):
        """
        Fetch only the medical reports that the patient has permitted for emergency access.
        """
        db = get_db()
        return db.execute("""
            SELECT * FROM medical_reports 
            WHERE user_id = ? AND (emergency_access_allowed = 1 OR emergency_access_allowed IS NULL)
            ORDER BY uploaded_at DESC
        """, (user_id,)).fetchall()

    @staticmethod
    def toggle_emergency_access(report_id, user_id):
        """
        Toggle whether a report is permitted to be viewed during emergency access.
        Ensures patients can only toggle permissions on their own documents.
        """
        db = get_db()
        report = ReportModel.get_user_report(report_id, user_id)
        if not report:
            return None

        current_val = report['emergency_access_allowed'] if 'emergency_access_allowed' in report.keys() and report['emergency_access_allowed'] is not None else 1
        new_val = 0 if current_val == 1 else 1

        db.execute("""
            UPDATE medical_reports
            SET emergency_access_allowed = ?
            WHERE id = ? AND user_id = ?
        """, (new_val, report_id, user_id))
        db.commit()
        return new_val

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
