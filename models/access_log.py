from database.db import get_db

class AccessLogModel:
    """Helper functions for logging and auditing emergency access events."""

    @staticmethod
    def log(user_id, action, status, token_id=None, token_identifier=None, ip_address=None, user_agent=None, report_id=None, resource_type='PROFILE', resource_id=None):
        """
        Record an emergency access attempt in SQLite.
        Actions: 'VIEW_PROFILE', 'DOWNLOAD_REPORT'
        Status: 'SUCCESS', 'EXPIRED', 'REVOKED', 'INVALID_TOKEN'
        """
        db = get_db()
        safe_ua = (user_agent[:180] + '...') if user_agent and len(user_agent) > 180 else user_agent
        eff_resource_id = resource_id if resource_id is not None else report_id
        eff_report_id = report_id if report_id is not None else (resource_id if resource_type == 'REPORT' else None)

        try:
            db.execute("""
                INSERT INTO access_logs (
                    user_id, token_id, token_identifier, action, status,
                    resource_type, resource_id, ip_address, user_agent, report_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                token_id,
                token_identifier,
                action,
                status,
                resource_type,
                eff_resource_id,
                ip_address or "Unknown",
                safe_ua or "Unknown",
                eff_report_id
            ))
        except Exception:
            # Fallback if columns are in legacy format
            db.execute("""
                INSERT INTO access_logs (
                    user_id, token_id, token_identifier, action, status,
                    ip_address, user_agent, report_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                token_id,
                token_identifier,
                action,
                status,
                ip_address or "Unknown",
                safe_ua or "Unknown",
                eff_report_id
            ))

        db.commit()

    @staticmethod
    def get_by_user_id(user_id, limit=30):
        """
        Fetch recent emergency access logs for the patient to audit who accessed their records.
        """
        db = get_db()
        return db.execute("""
            SELECT l.*, r.original_filename
            FROM access_logs l
            LEFT JOIN medical_reports r ON (l.report_id = r.id OR l.resource_id = r.id)
            WHERE l.user_id = ?
            ORDER BY l.accessed_at DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
