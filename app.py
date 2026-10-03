import os
from pathlib import Path
from flask import Flask, redirect, url_for
from config import Config
from database.db import close_db, init_db
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.profile import profile_bp
from routes.reports import reports_bp
from routes.emergency import emergency_bp

def create_app(config_class=Config):
    """Flask application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure uploads directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Register database teardown
    app.teardown_appcontext(close_db)

    # Ensure SQLite database tables exist
    init_db(app)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(emergency_bp)

    return app

app = create_app()

if __name__ == '__main__':
    # Run the application in debug mode for college demonstration
    app.run(host='127.0.0.1', port=5000, debug=True)
