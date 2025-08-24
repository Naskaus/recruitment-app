# app/staff/routes.py

from flask import (Blueprint, render_template, request, jsonify, redirect,
                   url_for, current_app, Response, send_from_directory, abort)
from flask_login import login_required, current_user
from app.models import db, StaffProfile, Assignment, User, PerformanceRecord, Venue
from werkzeug.utils import secure_filename
from datetime import datetime, date
import os
import uuid
from weasyprint import HTML
import pathlib

# Blueprint definition
staff_bp = Blueprint('staff', __name__, template_folder='../templates', url_prefix='/staff')

# --- Constants (to be moved later) ---
CONTRACT_TYPES = {"1jour": 1, "10jours": 10, "1mois": 30}
DRINK_STAFF_COMMISSION = 100
DRINK_BAR_PRICE = 120
ALLOWED_STATUSES = ["Active", "Working", "Quiet", "Screening", "Rejected", "Blacklisted"]

def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# --- VIEWS (HTML PAGES) ---

@staff_bp.route('/')
@login_required
def staff_list():
    """Displays the list of staff with sorting and searching, scoped by agency."""
    if not current_user.agency_id:
        abort(403, "User not associated with an agency.")

    search_nickname = request.args.get('search_nickname', '').strip()
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')

    query = StaffProfile.query.filter_by(agency_id=current_user.agency_id)

    if search_nickname:
        query = query.filter(StaffProfile.nickname.ilike(f'%{search_nickname}%'))

    sort_column_map = {
        'nickname': db.func.lower(StaffProfile.nickname),
        'age': StaffProfile.dob,
        'status': StaffProfile.status,
        'created_at': StaffProfile.created_at,
        'staff_id': StaffProfile.staff_id,
        'preferred_position': StaffProfile.preferred_position
    }
    sort_column = sort_column_map.get(sort_by, StaffProfile.created_at)

    effective_sort_order = sort_order
    if sort_by == 'age':
        effective_sort_order = 'asc' if sort_order == 'desc' else 'desc'

    if effective_sort_order == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    all_profiles = query.all()
    
    # Get venues for the current agency
    venues = Venue.query.filter_by(agency_id=current_user.agency_id).order_by(Venue.name).all()
    
    return render_template('staff_list.html', profiles=all_profiles, statuses=ALLOWED_STATUSES,
        venues=venues, current_filters={'search_nickname': search_nickname, 'sort_by': sort_by, 'sort_order': sort_order})

@staff_bp.route('/profile/new', methods=['GET'])
@staff_bp.route('/profile/<int:profile_id>/edit', methods=['GET'])
@login_required
def profile_form(profile_id=None):
    """Renders the form for both creating a new profile and editing an existing one."""
    if not current_user.agency_id:
        abort(403, "User not associated with an agency.")

    edit_mode = profile_id is not None
    profile = None
    if edit_mode:
        profile = StaffProfile.query.filter_by(id=profile_id, agency_id=current_user.agency_id).first_or_404()

    current_year = date.today().year
    years = range(current_year - 18, current_year - 60, -1)
    
    return render_template('profile_form.html', profile=profile, years=years, 
                           months=range(1, 13), days=range(1, 32), edit_mode=edit_mode)

@staff_bp.route('/profile/<int:profile_id>')
@login_required
def profile_detail(profile_id):
    """Displays the detailed view of a single staff profile."""
    if not current_user.agency_id:
        abort(403, "User not associated with an agency.")

    profile = StaffProfile.query.filter_by(id=profile_id, agency_id=current_user.agency_id).options(
        db.joinedload(StaffProfile.assignments).subqueryload(Assignment.performance_records)
    ).first_or_404()
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    start_date, end_date = None, None
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    all_assignments = sorted(profile.assignments, key=lambda a: a.start_date, reverse=True)
    
    assignments_to_process = all_assignments
    if start_date or end_date:
        assignments_to_process = [
            a for a in all_assignments
            if (not end_date or a.start_date <= end_date) and \
               (not start_date or a.end_date >= start_date)
        ]

    # --- KPI CALCULATION LOGIC ---
    total_days_worked = 0
    total_drinks_sold = 0
    total_special_comm = 0
    total_salary_paid = 0
    total_commission_paid = 0
    total_bar_profit = 0

    for assignment in assignments_to_process:
        original_duration = CONTRACT_TYPES.get(assignment.contract_type, 1)
        base_daily_salary = (assignment.base_salary / original_duration) if original_duration > 0 else 0

        records_to_process = assignment.performance_records
        if start_date or end_date:
            records_to_process = [
                r for r in assignment.performance_records 
                if (not start_date or r.record_date >= start_date) and \
                   (not end_date or r.record_date <= end_date)
            ]

        for record in records_to_process:
            daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
            daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
            bar_revenue = ((record.drinks_sold or 0) * DRINK_BAR_PRICE) + (record.special_commissions or 0)
            daily_profit = bar_revenue - daily_salary
            
            total_salary_paid += daily_salary
            total_commission_paid += daily_commission
            total_bar_profit += daily_profit
            total_drinks_sold += record.drinks_sold or 0
            total_special_comm += record.special_commissions or 0
        
        total_days_worked += len(records_to_process)

    history_stats = {
        "total_days_worked": total_days_worked,
        "total_drinks_sold": total_drinks_sold,
        "total_special_comm": total_special_comm,
        "total_salary_paid": total_salary_paid,
        "total_commission_paid": total_commission_paid,
        "total_bar_profit": total_bar_profit
    }
    
    return render_template('profile_detail.html', profile=profile, assignments=assignments_to_process, 
                           history_stats=history_stats, filter_start_date=start_date, filter_end_date=end_date)


# --- API (JSON ROUTES) ---

@staff_bp.route('/api/profile', methods=['POST'])
@login_required
def create_profile():
    """API endpoint to create a new profile."""
    if not current_user.agency_id:
        return jsonify({'status': 'error', 'message': 'User not associated with an agency.'}), 403

    data = request.form
    if not data.get('nickname'):
        return jsonify({'status': 'error', 'message': 'Nickname is required.'}), 400
    try:
        dob = date(int(data['dob_year']), int(data['dob_month']), int(data['dob_day']))
    except (ValueError, KeyError):
        return jsonify({'status': 'error', 'message': 'Invalid date of birth provided.'}), 400
        
    # --- FIX: Associate the new profile with the user's agency ---
    new_profile = StaffProfile(dob=dob, agency_id=current_user.agency_id)
    
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
            new_profile.photo_url = unique_filename
            
    db.session.add(new_profile)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Profile created successfully!', 'profile_id': new_profile.id}), 201

@staff_bp.route('/api/profile/<int:profile_id>', methods=['POST'])
@login_required
def update_profile(profile_id):
    """API endpoint to update an existing profile."""
    profile = StaffProfile.query.filter_by(id=profile_id, agency_id=current_user.agency_id).first_or_404()
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
            profile.photo_url = unique_filename
            
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Profile updated successfully!'}), 200

@staff_bp.route('/api/profile/<int:profile_id>/delete', methods=['POST'])
@login_required
def delete_profile(profile_id):
    """API endpoint to delete a profile."""
    profile = StaffProfile.query.filter_by(id=profile_id, agency_id=current_user.agency_id).first_or_404()
    if profile.photo_url and 'default' not in profile.photo_url:
        try:
            photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], profile.photo_url)
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
    profile = StaffProfile.query.filter_by(id=profile_id, agency_id=current_user.agency_id).first_or_404()
    data = request.get_json()
    new_status = data.get('status')
    if not new_status or new_status not in ALLOWED_STATUSES:
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
    try:
        profile = StaffProfile.query.filter_by(id=profile_id, agency_id=current_user.agency_id).first_or_404()
        photo_url_for_pdf = None
        if profile.photo_url and 'default' not in profile.photo_url:
            photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], profile.photo_url)
            if os.path.exists(photo_path):
                photo_url_for_pdf = pathlib.Path(photo_path).as_uri()
            
        # Re-run calculation logic for the PDF context
        total_days_worked, total_drinks_sold, total_special_comm, total_salary_paid, total_commission_paid, total_bar_profit = 0, 0, 0, 0, 0, 0
        
        # Calculate stats for each assignment and create a list with stats
        assignments_with_stats = []
        for assignment in profile.assignments:
            original_duration = CONTRACT_TYPES.get(assignment.contract_type, 1)
            base_daily_salary = (assignment.base_salary / original_duration) if original_duration > 0 else 0
            
            assignment_stats = {"drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0}
            
            for record in assignment.performance_records:
                daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
                daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
                bar_revenue = ((record.drinks_sold or 0) * DRINK_BAR_PRICE) + (record.special_commissions or 0)
                daily_profit = bar_revenue - daily_salary
                
                assignment_stats["drinks"] += record.drinks_sold or 0
                assignment_stats["special_comm"] += record.special_commissions or 0
                assignment_stats["salary"] += daily_salary
                assignment_stats["commission"] += daily_commission
                assignment_stats["profit"] += daily_profit
                
                total_salary_paid += daily_salary
                total_commission_paid += daily_commission
                total_bar_profit += daily_profit
                total_drinks_sold += record.drinks_sold or 0
                total_special_comm += record.special_commissions or 0
            
            total_days_worked += len(assignment.performance_records)
            
            # Create a dict with assignment and its stats
            assignments_with_stats.append({
                'assignment': assignment,
                'contract_stats': assignment_stats
            })

        history_stats = {
            "total_days_worked": total_days_worked, "total_drinks_sold": total_drinks_sold,
            "total_special_comm": total_special_comm, "total_salary_paid": total_salary_paid,
            "total_commission_paid": total_commission_paid, "total_bar_profit": total_bar_profit
        }

        rendered_html = render_template('profile_pdf.html', profile=profile, photo_url=photo_url_for_pdf,
                                        history_stats=history_stats, assignments=assignments_with_stats, 
                                        report_date=datetime.utcnow())
        
        # Generate PDF with better error handling
        try:
            pdf = HTML(string=rendered_html).write_pdf()
        except Exception as pdf_error:
            current_app.logger.error(f"PDF generation error for profile {profile_id}: {pdf_error}")
            return jsonify({'status': 'error', 'message': 'PDF generation failed. Please try again.'}), 500
        
        filename = f"profile_{secure_filename(profile.nickname)}_{date.today()}.pdf"
        
        response = Response(pdf, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.headers['Content-Length'] = len(pdf)
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error generating PDF for profile {profile_id}: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to generate PDF. Please try again.'}), 500