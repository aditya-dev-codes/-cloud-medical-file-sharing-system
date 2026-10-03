from database.db import get_db

class ProfileModel:
    """Helper functions for patient medical profiles."""

    @staticmethod
    def get_by_user_id(user_id):
        """Fetch the medical profile for a specific user ID."""
        db = get_db()
        return db.execute(
            "SELECT * FROM medical_profiles WHERE user_id = ?",
            (user_id,)
        ).fetchone()

    @staticmethod
    def update_profile(user_id, data):
        """
        Create or update the medical profile for a given user ID.
        Ensures users can only update their own profile record.
        """
        db = get_db()
        existing = db.execute(
            "SELECT id FROM medical_profiles WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        if existing:
            db.execute("""
                UPDATE medical_profiles
                SET full_name = ?,
                    date_of_birth = ?,
                    blood_group = ?,
                    allergies = ?,
                    current_medications = ?,
                    existing_conditions = ?,
                    previous_surgeries = ?,
                    emergency_contact_name = ?,
                    emergency_contact_phone = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (
                data.get('full_name', '').strip(),
                data.get('date_of_birth', '').strip(),
                data.get('blood_group', '').strip(),
                data.get('allergies', '').strip(),
                data.get('current_medications', '').strip(),
                data.get('existing_conditions', '').strip(),
                data.get('previous_surgeries', '').strip(),
                data.get('emergency_contact_name', '').strip(),
                data.get('emergency_contact_phone', '').strip(),
                user_id
            ))
        else:
            db.execute("""
                INSERT INTO medical_profiles (
                    user_id, full_name, date_of_birth, blood_group, allergies,
                    current_medications, existing_conditions, previous_surgeries,
                    emergency_contact_name, emergency_contact_phone
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                data.get('full_name', '').strip(),
                data.get('date_of_birth', '').strip(),
                data.get('blood_group', '').strip(),
                data.get('allergies', '').strip(),
                data.get('current_medications', '').strip(),
                data.get('existing_conditions', '').strip(),
                data.get('previous_surgeries', '').strip(),
                data.get('emergency_contact_name', '').strip(),
                data.get('emergency_contact_phone', '').strip()
            ))

        db.commit()
        return True
