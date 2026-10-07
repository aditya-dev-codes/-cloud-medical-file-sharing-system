import sqlite3
from flask import g, current_app
from pathlib import Path

def get_db():
    """
    Get a database connection for the current application context.
    Reuses connection if already opened in the same request.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE']
        )
        # Enable column access by name (e.g., row['username'])
        g.db.row_factory = sqlite3.Row
        # Enable foreign key constraint enforcement in SQLite
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def migrate_db(db):
    """Safely apply incremental column additions to existing tables without data loss."""
    import hashlib

    # 1. medical_reports: emergency_access_allowed
    try:
        cols = [r['name'] for r in db.execute("PRAGMA table_info(medical_reports)").fetchall()]
        if cols and 'emergency_access_allowed' not in cols:
            db.execute("ALTER TABLE medical_reports ADD COLUMN emergency_access_allowed INTEGER DEFAULT 1")
    except Exception:
        pass

    # 2. emergency_tokens: token_hash, token_prefix, is_active, access_count, last_accessed_at, revoked_at
    try:
        cols = [r['name'] for r in db.execute("PRAGMA table_info(emergency_tokens)").fetchall()]
        if cols:
            if 'token_hash' not in cols:
                db.execute("ALTER TABLE emergency_tokens ADD COLUMN token_hash TEXT")
            if 'token_prefix' not in cols:
                db.execute("ALTER TABLE emergency_tokens ADD COLUMN token_prefix TEXT")
            if 'revoked_at' not in cols:
                db.execute("ALTER TABLE emergency_tokens ADD COLUMN revoked_at TIMESTAMP")
            if 'is_active' not in cols:
                db.execute("ALTER TABLE emergency_tokens ADD COLUMN is_active INTEGER DEFAULT 1")
            if 'access_count' not in cols:
                db.execute("ALTER TABLE emergency_tokens ADD COLUMN access_count INTEGER DEFAULT 0")
            if 'last_accessed_at' not in cols:
                db.execute("ALTER TABLE emergency_tokens ADD COLUMN last_accessed_at TIMESTAMP")

            # Upgrade any unhashed tokens if present
            existing_tokens = db.execute("SELECT id, token FROM emergency_tokens WHERE token_hash IS NULL").fetchall()
            for row in existing_tokens:
                raw = row['token'] or ''
                h = hashlib.sha256(raw.encode('utf-8')).hexdigest()
                p = raw[:8] if len(raw) >= 8 else raw
                db.execute("UPDATE emergency_tokens SET token_hash = ?, token_prefix = ? WHERE id = ?", (h, p, row['id']))
    except Exception:
        pass

    # 3. access_logs: resource_type, resource_id
    try:
        cols = [r['name'] for r in db.execute("PRAGMA table_info(access_logs)").fetchall()]
        if cols:
            if 'resource_type' not in cols:
                db.execute("ALTER TABLE access_logs ADD COLUMN resource_type TEXT DEFAULT 'PROFILE'")
            if 'resource_id' not in cols:
                db.execute("ALTER TABLE access_logs ADD COLUMN resource_id INTEGER")
    except Exception:
        pass

    db.commit()

def init_db(app):
    """Initialize database tables using schema.sql and apply schema migrations."""
    with app.app_context():
        db = get_db()
        schema_path = Path(__file__).parent / 'schema.sql'
        with open(schema_path, 'r', encoding='utf-8') as f:
            db.executescript(f.read())
        migrate_db(db)

