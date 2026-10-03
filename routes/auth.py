import functools
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from models.user import UserModel
from database.db import get_db

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def login_required(view):
    """Decorator to require login before accessing protected views."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view

@auth_bp.before_app_request
def load_logged_in_user():
    """Load current user info into Flask 'g' before handling any request."""
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = UserModel.get_by_id(user_id)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle new patient/user registration."""
    # If already logged in, redirect to dashboard
    if session.get('user_id'):
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        # Validation
        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return render_template('auth/register.html', username=username, email=email)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('auth/register.html', username=username, email=email)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('auth/register.html', username=username, email=email)

        if UserModel.get_by_username(username):
            flash("Username already taken. Please choose another.", "danger")
            return render_template('auth/register.html', email=email)

        if UserModel.get_by_email(email):
            flash("Email already registered. Please log in or use another email.", "danger")
            return render_template('auth/register.html', username=username)

        # Create user
        user_id = UserModel.create_user(username, email, password)
        if user_id:
            # Create initial blank medical profile row for this user
            db = get_db()
            db.execute("INSERT OR IGNORE INTO medical_profiles (user_id) VALUES (?)", (user_id,))
            db.commit()

            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash("Registration failed due to a database error. Please try again.", "danger")

    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login and session initialization."""
    # If already logged in, redirect to dashboard
    if session.get('user_id'):
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '').strip()

        if not identifier or not password:
            flash("Please enter both username/email and password.", "danger")
            return render_template('auth/login.html', identifier=identifier)

        # Allow login with either username or email
        user = UserModel.get_by_username(identifier)
        if not user:
            user = UserModel.get_by_email(identifier)

        if user and UserModel.verify_password(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for('dashboard.index'))
        else:
            flash("Invalid username/email or password.", "danger")

    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    """Clear session and log the user out."""
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for('auth.login'))
