from flask import Blueprint, render_template, session, g
from routes.auth import login_required
from database.db import get_db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    """Expanded user dashboard displaying health modules and action cards."""
    user_id = session.get('user_id')
    db = get_db()
    
    # 1. Fetch user's medical profile
    profile = db.execute(
        "SELECT * FROM medical_profiles WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    
    # 2. Fetch report count & recent uploaded reports
    report_count = db.execute(
        "SELECT COUNT(*) as count FROM medical_reports WHERE user_id = ?",
        (user_id,)
    ).fetchone()['count']
    
    recent_reports = db.execute(
        "SELECT * FROM medical_reports WHERE user_id = ? ORDER BY uploaded_at DESC LIMIT 5",
        (user_id,)
    ).fetchall()

    # 3. Fetch count of AI summaries generated
    summary_count = db.execute("""
        SELECT COUNT(*) as count 
        FROM ai_summaries s
        JOIN medical_reports r ON s.report_id = r.id
        WHERE r.user_id = ?
    """, (user_id,)).fetchone()['count']

    # 4. Fetch active emergency token and recent audit logs
    from models.token import TokenModel
    from models.access_log import AccessLogModel
    active_token = TokenModel.get_active_token(user_id)
    recent_access_logs = AccessLogModel.get_by_user_id(user_id, limit=5)

    return render_template(
        'dashboard/index.html',
        profile=profile,
        report_count=report_count,
        recent_reports=recent_reports,
        summary_count=summary_count,
        active_token=active_token,
        recent_access_logs=recent_access_logs
    )
