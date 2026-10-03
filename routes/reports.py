from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, abort, current_app
from pathlib import Path
from routes.auth import login_required
from models.report import ReportModel
from models.summary import SummaryModel
from services.storage import LocalStorageService
from services.text_extractor import TextExtractor
from services.ai_service import get_ai_service
from database.db import get_db

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
def list_reports():
    """List all medical reports uploaded by the logged-in patient."""
    user_id = session.get('user_id')
    reports = ReportModel.get_by_user_id(user_id)
    return render_template('reports/list.html', reports=reports)

@reports_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload a new medical report (PDF or TXT) with validation."""
    user_id = session.get('user_id')

    if request.method == 'POST':
        if 'report_file' not in request.files:
            flash("No file part in upload request.", "danger")
            return redirect(request.url)

        file = request.files['report_file']
        if file.filename == '':
            flash("Please choose a file to upload.", "danger")
            return redirect(request.url)

        try:
            # 1. Save file to storage abstraction
            file_meta = LocalStorageService.save_file(file, user_id)

            # 2. Save metadata to database
            report_id = ReportModel.create(
                user_id=user_id,
                filename=file_meta['filename'],
                original_filename=file_meta['original_filename'],
                file_path=file_meta['file_path'],
                file_size=file_meta['file_size'],
                file_type=file_meta['file_type']
            )

            flash(f"Report '{file_meta['original_filename']}' uploaded successfully!", "success")
            return redirect(url_for('reports.view_report', report_id=report_id))

        except ValueError as e:
            flash(str(e), "danger")
            return redirect(request.url)
        except Exception as e:
            flash(f"Upload failed: {str(e)}", "danger")
            return redirect(request.url)

    return render_template('reports/upload.html')

@reports_bp.route('/<int:report_id>')
@login_required
def view_report(report_id):
    """View report details, metadata, and AI summary status."""
    user_id = session.get('user_id')
    report = ReportModel.get_user_report(report_id, user_id)
    if not report:
        flash("Report not found or you are not authorized to view it.", "danger")
        return redirect(url_for('reports.list_reports'))

    # Fetch AI summary if generated
    db = get_db()
    ai_summary = db.execute(
        "SELECT * FROM ai_summaries WHERE report_id = ?",
        (report_id,)
    ).fetchone()

    return render_template('reports/view.html', report=report, ai_summary=ai_summary)

@reports_bp.route('/<int:report_id>/summarize', methods=['POST'])
@login_required
def summarize_report(report_id):
    """Extract document text and generate concise clinical summary via AI service."""
    user_id = session.get('user_id')
    report = ReportModel.get_user_report(report_id, user_id)
    if not report:
        flash("Report not found or access denied.", "danger")
        return redirect(url_for('reports.list_reports'))

    try:
        # 1. Resolve safe absolute file path
        abs_path = LocalStorageService.get_absolute_path(report['file_path'])
        
        # 2. Extract plain text from PDF or TXT
        extracted_text = TextExtractor.extract_text(abs_path, report['file_type'])

        # 3. Call modular AI Summarization service
        ai_service = get_ai_service(current_app.config)
        summary_result = ai_service.summarize(extracted_text, report['original_filename'])

        # 4. Save summary record into SQLite
        SummaryModel.create_or_update(
            report_id=report['id'],
            summary_text=summary_result['summary_text'],
            conditions=summary_result['extracted_conditions'],
            allergies=summary_result['extracted_allergies'],
            medications=summary_result['extracted_medications'],
            is_mock=summary_result['is_mock']
        )

        mode_label = "Local Mock AI" if summary_result['is_mock'] else "Live AI API"
        flash(f"Clinical summary generated successfully ({mode_label})!", "success")

    except Exception as e:
        flash(f"AI Summarization could not be completed: {str(e)}", "danger")

    return redirect(url_for('reports.view_report', report_id=report_id))

@reports_bp.route('/<int:report_id>/download')
@login_required
def download_report(report_id):
    """Securely stream or download the original file to authorized user."""
    user_id = session.get('user_id')
    report = ReportModel.get_user_report(report_id, user_id)
    if not report:
        abort(404, description="File not found or access denied.")

    try:
        abs_path = LocalStorageService.get_absolute_path(report['file_path'])
        if not abs_path.exists():
            flash("The physical file is missing from storage.", "danger")
            return redirect(url_for('reports.list_reports'))

        # Set mime type
        mimetype = 'application/pdf' if report['file_type'] == 'PDF' else 'text/plain'
        return send_file(
            str(abs_path),
            as_attachment=False,
            mimetype=mimetype,
            download_name=report['original_filename']
        )
    except Exception as e:
        flash(f"Error accessing file: {str(e)}", "danger")
        return redirect(url_for('reports.list_reports'))

@reports_bp.route('/<int:report_id>/delete', methods=['POST'])
@login_required
def delete_report(report_id):
    """Delete a medical report from database and local storage."""
    user_id = session.get('user_id')
    
    # Verify ownership before deleting
    report = ReportModel.get_user_report(report_id, user_id)
    if not report:
        flash("You are not authorized to delete this report.", "danger")
        return redirect(url_for('reports.list_reports'))

    # Remove physical file
    LocalStorageService.delete_file(report['file_path'])

    # Remove database record (cascading deletes AI summary too)
    ReportModel.delete(report_id, user_id)

    flash(f"Report '{report['original_filename']}' was deleted.", "info")
    return redirect(url_for('reports.list_reports'))
