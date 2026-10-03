from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from routes.auth import login_required
from models.profile import ProfileModel

profile_bp = Blueprint('profile', __name__, url_prefix='/profile')

VALID_BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'Unknown']

@profile_bp.route('/')
@login_required
def view():
    """Display the authenticated user's medical profile."""
    user_id = session.get('user_id')
    profile = ProfileModel.get_by_user_id(user_id)
    return render_template('profile/view.html', profile=profile)

@profile_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    """Allow user to edit their medical profile details."""
    user_id = session.get('user_id')
    
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        date_of_birth = request.form.get('date_of_birth', '').strip()
        blood_group = request.form.get('blood_group', '').strip()
        allergies = request.form.get('allergies', '').strip()
        current_medications = request.form.get('current_medications', '').strip()
        existing_conditions = request.form.get('existing_conditions', '').strip()
        previous_surgeries = request.form.get('previous_surgeries', '').strip()
        emergency_contact_name = request.form.get('emergency_contact_name', '').strip()
        emergency_contact_phone = request.form.get('emergency_contact_phone', '').strip()

        # Validate blood group if specified
        if blood_group and blood_group not in VALID_BLOOD_GROUPS:
            flash("Please select a valid blood group.", "danger")
            profile_data = request.form
            return render_template('profile/edit.html', profile=profile_data, blood_groups=VALID_BLOOD_GROUPS)

        data = {
            'full_name': full_name,
            'date_of_birth': date_of_birth,
            'blood_group': blood_group,
            'allergies': allergies,
            'current_medications': current_medications,
            'existing_conditions': existing_conditions,
            'previous_surgeries': previous_surgeries,
            'emergency_contact_name': emergency_contact_name,
            'emergency_contact_phone': emergency_contact_phone
        }

        ProfileModel.update_profile(user_id, data)
        flash("Medical profile updated successfully.", "success")
        return redirect(url_for('profile.view'))

    profile = ProfileModel.get_by_user_id(user_id)
    return render_template('profile/edit.html', profile=profile, blood_groups=VALID_BLOOD_GROUPS)
