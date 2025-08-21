# app/staff/routes.py

from flask import (Blueprint, render_template, request, jsonify, redirect,
                   url_for, current_app, Response, send_from_directory)
from flask_login import login_required
from app.models import db, StaffProfile, Assignment, User
from werkzeug.utils import secure_filename
from datetime import datetime, date
import os
import uuid
from weasyprint import HTML
import pathlib

# Blueprint definition
staff_bp = Blueprint('staff', __name__, template_folder='../templates', url_prefix='/staff')

def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# --- VIEWS (HTML PAGES) ---

@staff_bp.route('/')
@login_required
def staff_list():
    """Displays the list of staff with sorting and searching."""
    search_nickname = request.args.get('search_nickname', '').strip()
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')

    query = StaffProfile.query

    if search_nickname:
        query = query.filter(StaffProfile.nickname.ilike(f'%{search_nickname}%'))

    sort_column_map = {
        'nickname': db.func.lower(StaffProfile.nickname),
        'age': StaffProfile.dob,
        'status': StaffProfile.status,
        'created_at': StaffProfile.created_at
    }
    sort_column = sort_column_map.get(sort_by, StaffProfile.created_at)

    # Reverse sorting order for age (newer DOB = younger)
    if sort_by == 'age':
        effective_sort_order = 'asc' if sort_order == 'desc' else 'desc'
    else:
        effective_sort_order = sort_order

    if effective_sort_order == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    all_profiles = query.all()
    return render_template('staff_list.html', profiles=all_profiles, statuses=["Active", "Working", "Quiet"],
        current_filters={'search_nickname': search_nickname, 'sort_by': sort_by, 'sort_order': sort_order})

# IMPROVED: Two routes now point to this single, more robust function
@staff_bp.route('/profile/new', methods=['GET'])
@staff_bp.route('/profile/<int:profile_id>/edit', methods=['GET'])
@login_required
def profile_form(profile_id=None):
    """Renders the form for both creating a new profile and editing an existing one."""
    edit_mode = profile_id is not None
    profile = StaffProfile.query.get_or_404(profile_id) if edit_mode else None
    
    current_year = date.today().year
    years = range(current_year - 18, current_year - 60, -1)
    
    return render_template('profile_form.html', profile=profile, years=years, 
                           months=range(1, 13), days=range(1, 32), edit_mode=edit_mode)

@staff_bp.route('/profile/<int:profile_id>')
@login_required
def profile_detail(profile_id):
    """Displays the detailed view of a single staff profile."""
    profile = StaffProfile.query.options(
        db.joinedload(StaffProfile.assignments).subqueryload(Assignment.performance_records)
    ).get_or_404(profile_id)
    
    # Placeholder for stats logic
    history_stats = {'total_days_worked': 0, 'total_drinks_sold': 0, 'total_salary_paid': 0,
                     'total_commission_paid': 0, 'total_special_comm': 0, 'total_bar_profit': 0}
    
    return render_template('profile_detail.html', profile=profile, assignments=profile.assignments, 
                           history_stats=history_stats, filter_start_date=None, filter_end_date=None)

# --- API (JSON ROUTES) ---

@staff_bp.route('/api/profile', methods=['POST'])
@login_required
def create_profile():
    """API endpoint to create a new profile."""
    data = request.form
    if not data.get('nickname'):
        return jsonify({'status': 'error', 'message': 'Nickname is required.'}), 400
    try:
        dob = date(int(data['dob_year']), int(data['dob_month']), int(data['dob_day']))
    except (ValueError, KeyError):
        return jsonify({'status': 'error', 'message': 'Invalid date of birth provided.'}), 400
        
    new_profile = StaffProfile(dob=dob)
    for key, value in data.items():
        if hasattr(new_profile, key) and value:
            setattr(new_profile, key, value)
            
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(save_path)
            new_profile.photo_url = url_for('staff.uploaded_file', filename=unique_filename)
            
    db.session.add(new_profile)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Profile created successfully!', 'profile_id': new_profile.id}), 201

@staff_bp.route('/api/profile/<int:profile_id>', methods=['POST'])
@login_required
def update_profile(profile_id):
    """API endpoint to update an existing profile."""
    profile = StaffProfile.query.get_or_404(profile_id)
    data = request.form
    for key, value in data.items():
        if hasattr(profile, key) and key not in ['dob_day', 'dob_month', 'dob_year']:
            setattr(profile, key, value or None)
    try:
        dob = date(int(data['dob_year']), int(data['dob_month']), int(data['dob_day']))
        profile.dob = dob
    except (ValueError, KeyError):
        pass # Ignore if DOB is not provided or invalid
        
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(save_path)
            profile.photo_url = url_for('staff.uploaded_file', filename=unique_filename)
            
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Profile updated successfully!'}), 200

@staff_bp.route('/api/profile/<int:profile_id>/delete', methods=['POST'])
@login_required
def delete_profile(profile_id):
    """API endpoint to delete a profile."""
    profile = StaffProfile.query.get_or_404(profile_id)
    if profile.photo_url:
        try:
            photo_filename = os.path.basename(profile.photo_url)
            photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], photo_filename)
            if os.path.exists(photo_path):
                os.remove(photo_path)
        except Exception as e:
            current_app.logger.error(f"Error deleting photo file: {e}")
    db.session.delete(profile)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Profile deleted successfully.'})

@staff_bp.route('/api/profile/<int:profile_id>/status', methods=['POST'])
@login_required
def update_staff_status(profile_id):
    """API endpoint to update a staff member's status."""
    profile = StaffProfile.query.get_or_404(profile_id)
    data = request.get_json()
    new_status = data.get('status')
    if not new_status or new_status not in ["Active", "Working", "Quiet"]:
        return jsonify({'status': 'error', 'message': 'Invalid status provided.'}), 400
    profile.status = new_status
    db.session.commit()
    return jsonify({'status': 'success', 'message': f'Status for {profile.nickname} updated to {new_status}.'})

# --- PDF & FILES ---

@staff_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serves uploaded files."""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@staff_bp.route('/profile/<int:profile_id>/pdf')
@login_required
def profile_pdf(profile_id):
    """Generates a PDF report for a staff profile."""
    profile = StaffProfile.query.get_or_404(profile_id)
    photo_url = None
    if profile.photo_url:
        photo_filename = os.path.basename(profile.photo_url)
        photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], photo_filename)
        if os.path.exists(photo_path):
            photo_url = pathlib.Path(photo_path).as_uri()
            
    # Placeholder for stats logic
    history_stats = {'total_days_worked': 0, 'total_drinks_sold': 0, 'total_salary_paid': 0, 
                     'total_commission_paid': 0, 'total_special_comm': 0, 'total_bar_profit': 0}

    rendered_html = render_template('pdf/profile_pdf.html', profile=profile, photo_url=photo_url,
                                    history_stats=history_stats, assignments=profile.assignments, 
                                    report_date=datetime.utcnow())
    
    pdf = HTML(string=rendered_html).write_pdf()
    filename = f"profile_{secure_filename(profile.nickname)}_{date.today()}.pdf"
    
    return Response(pdf, mimetype='application/pdf', 
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})