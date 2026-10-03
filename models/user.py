from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db

class UserModel:
    """Helper functions for user authentication and management."""

    @staticmethod
    def create_user(username, email, password):
        """
        Creates a new user with hashed password.
        Returns the new user ID, or None if creation fails.
        """
        db = get_db()
        password_hash = generate_password_hash(password)
        try:
            cursor = db.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username.strip(), email.strip().lower(), password_hash)
            )
            db.commit()
            return cursor.lastrowid
        except Exception:
            db.rollback()
            return None

    @staticmethod
    def get_by_id(user_id):
        """Retrieve user row by user ID."""
        db = get_db()
        return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    @staticmethod
    def get_by_username(username):
        """Retrieve user row by username (case-insensitive lookup)."""
        db = get_db()
        return db.execute(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)",
            (username.strip(),)
        ).fetchone()

    @staticmethod
    def get_by_email(email):
        """Retrieve user row by email."""
        db = get_db()
        return db.execute(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(?)",
            (email.strip(),)
        ).fetchone()

    @staticmethod
    def verify_password(stored_hash, password):
        """Compares plain password against stored hash."""
        return check_password_hash(stored_hash, password)
