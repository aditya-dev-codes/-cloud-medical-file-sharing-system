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

def init_db(app):
    """Initialize database tables using schema.sql."""
    with app.app_context():
        db = get_db()
        schema_path = Path(__file__).parent / 'schema.sql'
        with open(schema_path, 'r', encoding='utf-8') as f:
            db.executescript(f.read())
        db.commit()
