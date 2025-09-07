# app/staff/routes.py

from flask import (Blueprint, render_template, request, jsonify, redirect,
                   url_for, current_app, Response, send_from_directory, abort)
from flask_login import login_required, current_user
from app.models import db, StaffProfile, Assignment, User, PerformanceRecord, Venue
from app.decorators import admin_required, manager_required, super_admin_required, webdev_required, staff_management_required
from werkzeug.utils import secure_filename
from datetime import datetime, date
import os
import uuid
from weasyprint import HTML
import pathlib

# Helper function to get current agency ID
def get_current_agency_id():
    """Get the current agency ID for the user, handling WebDev users properly."""
    from flask import session
    
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
        from app.models import Agency
        # If we have an agency_id, verify it's active
        if agency_id:
            active = Agency.query.filter_by(id=agency_id, is_deleted=False).first()
            if not active:
                # Clear invalid session agency and try to fallback
                session.pop('current_agency_id', None)
                session.pop('current_agency_name', None)
                agency_id = None
        # For WebDev, if no agency is selected, use the first available active agency
        if not agency_id:
            first_agency = Agency.query.filter_by(is_deleted=False).first()
            if first_agency:
                agency_id = first_agency.id
                session['current_agency_id'] = agency_id
                session['current_agency_name'] = first_agency.name
            else:
                abort(403, "This agency no longer exists. Please contact your manager.")
        return agency_id
    else:
        agency_id = current_user.agency_id
        if not agency_id:
            abort(403, "User not associated with an agency.")
        # Ensure the user's agency is active (not soft-deleted)
        from app.models import Agency
        active = Agency.query.filter_by(id=agency_id, is_deleted=False).first()
        if not active:
            abort(403, "This agency no longer exists. Please contact your manager.")
        return agency_id

# Blueprint definition
staff_bp = Blueprint('staff', __name__, template_folder='../templates', url_prefix='/staff')

# --- Constants (to be moved later) ---
CONTRACT_TYPES = {"1day": 1, "10days": 10, "1month": 30}
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
@admin_required
def staff_list():
    """Displays the list of staff with sorting and searching, scoped by agency."""
    agency_id = get_current_agency_id()

    search_nickname = request.args.get('search_nickname', '').strip()
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')

    query = StaffProfile.query.filter_by(agency_id=agency_id)

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
    venues = Venue.query.filter_by(agency_id=agency_id).order_by(Venue.name).all()
    
    return render_template('staff_list.html', profiles=all_profiles, statuses=ALLOWED_STATUSES,
        venues=venues, current_filters={'search_nickname': search_nickname, 'sort_by': sort_by, 'sort_order': sort_order})

@staff_bp.route('/profile/new', methods=['GET'])
@staff_bp.route('/profile/<int:profile_id>/edit', methods=['GET'])
@login_required
@admin_required
def profile_form(profile_id=None):
    """Renders the form for both creating a new profile and editing an existing one."""
    from app.models import AgencyPosition
    
    agency_id = get_current_agency_id()

    edit_mode = profile_id is not None
    profile = None
    if edit_mode:
        profile = StaffProfile.query.filter_by(id=profile_id, agency_id=agency_id).first_or_404()

    # Get agency positions for the dropdown
    agency_positions = AgencyPosition.query.filter_by(agency_id=agency_id).order_by(AgencyPosition.name).all()

    current_year = date.today().year
    years = range(current_year - 18, current_year - 60, -1)
    
    # DIAGNOSTIC CODE - TEMPORARY - ENHANCED
    try:
        from flask import current_app
        import os
        template_folder = current_app.template_folder
        absolute_template_path = os.path.abspath(template_folder)
        profile_form_path = os.path.join(absolute_template_path, 'profile_form.html')
        
        print("=" * 80)
        print("🔍 FLASK TEMPLATE DIAGNOSTIC - ENHANCED")
        print("=" * 80)
        print(f"Template folder: {absolute_template_path}")
        print(f"Profile form path: {profile_form_path}")
        print(f"File exists: {os.path.exists(profile_form_path)}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"App instance folder: {current_app.instance_path}")
        print("=" * 80)
        
        # Force flush to ensure output appears
        import sys
        sys.stdout.flush()
        
    except Exception as e:
        print(f"🚨 DIAGNOSTIC ERROR: {e}")
        import sys
        sys.stdout.flush()
    
    return render_template('profile_form.html', profile=profile, years=years, 
                           months=range(1, 13), days=range(1, 32), edit_mode=edit_mode,
                           agency_positions=agency_positions)

@staff_bp.route('/profile/<int:profile_id>')
@login_required
@admin_required
def profile_detail(profile_id):
    """Displays the detailed view of a single staff profile."""
    from app.services.payroll_service import get_staff_performance_summary
    
    agency_id = get_current_agency_id()

    profile = StaffProfile.query.filter_by(id=profile_id, agency_id=agency_id).options(
        db.joinedload(StaffProfile.assignments).subqueryload(Assignment.performance_records)
    ).first_or_404()
    
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    start_date, end_date = None, None
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    # Utiliser le service de paie pour obtenir les statistiques de performance
    try:
        performance_summary = get_staff_performance_summary(profile_id, start_date, end_date)
        history_stats = performance_summary['summary_totals']
        detailed_history = performance_summary['detailed_history']
        contract_calculations = performance_summary['contract_calculations']
    except Exception as e:
        # Fallback en cas d'erreur
        history_stats = {
            "total_days_worked": 0,
            "total_drinks_sold": 0,
            "total_special_comm": 0,
            "total_salary_paid": 0,
            "total_commission_paid": 0,
            "total_bar_profit": 0
        }
        detailed_history = []
        contract_calculations = []
        print(f"Erreur lors du calcul des statistiques de performance: {str(e)}")

    # Filtrer les assignments pour l'affichage
    all_assignments = sorted(profile.assignments, key=lambda a: a.start_date, reverse=True)
    
    assignments_to_process = all_assignments
    if start_date or end_date:
        assignments_to_process = [
            a for a in all_assignments
            if (not end_date or a.start_date <= end_date) and \
               (not start_date or a.end_date >= start_date)
        ]
    
    return render_template('profile_detail.html', profile=profile, assignments=assignments_to_process, 
                           history_stats=history_stats, filter_start_date=start_date, filter_end_date=end_date,
                           detailed_history=detailed_history, contract_calculations=contract_calculations)


# --- API (JSON ROUTES) ---

@staff_bp.route('/api/profile', methods=['POST'])
@login_required
@admin_required
def create_profile():
    """API endpoint to create a new profile."""
    from flask import session
    
    # Get current agency ID
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        return jsonify({'status': 'error', 'message': 'User not associated with an agency.'}), 403

    data = request.form
    if not data.get('nickname'):
        return jsonify({'status': 'error', 'message': 'Nickname is required.'}), 400
    try:
        dob = date(int(data['dob_year']), int(data['dob_month']), int(data['dob_day']))
    except (ValueError, KeyError):
        return jsonify({'status': 'error', 'message': 'Invalid date of birth provided.'}), 400
        
    # --- FIX: Associate the new profile with the user's agency ---
    new_profile = StaffProfile(dob=dob, agency_id=agency_id)
    
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
    from flask import session
    
    # Get current agency ID
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    profile = StaffProfile.query.filter_by(id=profile_id, agency_id=agency_id).first_or_404()
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
@staff_management_required
def delete_staff_profile(profile_id):
    """Delete a staff profile with proper security checks and relationship cleanup."""
    from app.models import Assignment, PerformanceRecord, ContractCalculations
    
    # Get current agency ID
    agency_id = get_current_agency_id()
    
    # Get the profile to delete
    profile_to_delete = StaffProfile.query.filter_by(id=profile_id, agency_id=agency_id).first_or_404()
    
    # Store profile info for response
    profile_nickname = profile_to_delete.nickname
    
    try:
        # Clean up related data before deletion
        # 1. Update assignments where this staff is assigned (set staff_id to None)
        assignments_to_update = Assignment.query.filter_by(staff_id=profile_id).all()
        for assignment in assignments_to_update:
            assignment.staff_id = None
            # Also archive staff info in the assignment
            assignment.archived_staff_name = profile_nickname
            assignment.archived_staff_photo = profile_to_delete.photo_url
        
        # 2. Delete performance records (they will be deleted automatically due to cascade)
        # This is handled by the cascade="all, delete-orphan" in the Assignment model
        
        # 3. Delete contract calculations (they will be deleted automatically due to cascade)
        # This is handled by the cascade="all, delete-orphan" in the Assignment model
        
        # Delete the profile
        db.session.delete(profile_to_delete)
        db.session.commit()
        
        return jsonify({
            'status': 'success', 
            'message': f'Profil "{profile_nickname}" a été supprimé avec succès.'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting staff profile {profile_id}: {e}")
        return jsonify({
            'status': 'error', 
            'message': 'Une erreur est survenue lors de la suppression du profil. Veuillez réessayer.'
        }), 500

@staff_bp.route('/api/profile/<int:profile_id>/status', methods=['POST'])
@login_required
def update_staff_status(profile_id):
    """API endpoint to update a staff member's status."""
    from flask import session
    
    # Get current agency ID
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    profile = StaffProfile.query.filter_by(id=profile_id, agency_id=agency_id).first_or_404()
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
    print(f"DEBUG: Generating PDF for profile {profile_id} with args: {request.args}")  # <--- TRACE DE DÉBOGAGE
    from flask import session
    from app.services.payroll_service import get_staff_performance_summary
    
    # Get current agency ID
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    try:
        profile = StaffProfile.query.filter_by(id=profile_id, agency_id=agency_id).first_or_404()
        photo_url_for_pdf = None
        if profile.photo_url and 'default' not in profile.photo_url:
            photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], profile.photo_url)
            if os.path.exists(photo_path):
                photo_url_for_pdf = pathlib.Path(photo_path).as_uri()
        
        # Récupérer les paramètres de filtre de date depuis la requête
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        start_date, end_date = None, None
        if start_date_str and start_date_str != '':
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if end_date_str and end_date_str != '':
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
        # Utiliser le service de paie pour obtenir les statistiques de performance
        try:
            performance_summary = get_staff_performance_summary(profile_id, start_date, end_date)
            history_stats = performance_summary['summary_totals']
            detailed_history = performance_summary.get('detailed_history', [])
            contract_calculations = performance_summary['contract_calculations']
        except Exception as e:
            # Fallback en cas d'erreur
            history_stats = {
                "total_days_worked": 0,
                "total_drinks_sold": 0,
                "total_special_comm": 0,
                "total_salary_paid": 0,
                "total_commission_paid": 0,
                "total_bar_profit": 0
            }
            detailed_history = []
            contract_calculations = []
            current_app.logger.error(f"Erreur lors du calcul des statistiques de performance pour le PDF: {str(e)}")

        # Préparer les assignments avec leurs statistiques pour le PDF
        assignments_with_stats = []
        
        # Trier les assignements par date de début (du plus récent au plus ancien)
        sorted_assignments = sorted(profile.assignments, key=lambda a: a.start_date, reverse=True)
        
        # Filtrer les assignements en fonction des dates de filtre
        if start_date or end_date:
            sorted_assignments = [
                a for a in sorted_assignments
                if (start_date is None or a.end_date >= start_date) and \
                   (end_date is None or a.start_date <= end_date)
            ]
        
        for assignment in sorted_assignments:
            # Chercher les calculs de contrat pour cet assignment
            assignment_calc = next((calc for calc in contract_calculations if calc['assignment_id'] == assignment.id), None)
            
            if assignment_calc:
                assignment_stats = {
                    "days_worked": assignment_calc['days_worked'],
                    "drinks": assignment_calc['total_drinks'],
                    "special_comm": assignment_calc['total_special_comm'],
                    "salary": assignment_calc['total_salary'],
                    "commission": assignment_calc['total_commission'],
                    "profit": assignment_calc['total_profit']
                }
            else:
                # Fallback si pas de calculs disponibles
                assignment_stats = {
                    "days_worked": 0, 
                    "drinks": 0, 
                    "special_comm": 0, 
                    "salary": 0, 
                    "commission": 0, 
                    "profit": 0
                }
            
            # Ne pas inclure les assignements sans jour travaillé si un filtre de date est actif
            if (start_date or end_date) and assignment_stats['days_worked'] == 0:
                continue
                
            assignments_with_stats.append({
                'assignment': assignment,
                'contract_stats': assignment_stats
            })

        # Trier l'historique détaillé par date décroissante
        detailed_history = sorted(detailed_history, key=lambda x: x.get('record_date', ''), reverse=True)

        rendered_html = render_template('profile_pdf.html', 
                                      profile=profile, 
                                      photo_url=photo_url_for_pdf,
                                      history_stats=history_stats, 
                                      detailed_history=detailed_history,
                                      assignments=assignments_with_stats, 
                                      report_date=datetime.utcnow(),
                                      filter_start_date=start_date,
                                      filter_end_date=end_date)
        
        # Generate PDF with better error handling
        try:
            pdf = HTML(string=rendered_html).write_pdf()
        except Exception as pdf_error:
            current_app.logger.error(f"PDF generation error for profile {profile_id}: {pdf_error}")
            return jsonify({'status': 'error', 'message': 'PDF generation failed. Please try again.'}), 500
        
        filename = f"profile_{secure_filename(profile.nickname)}_{date.today()}.pdf"
        
        response = Response(pdf, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
        response.headers['Content-Length'] = len(pdf)
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error generating PDF for profile {profile_id}: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to generate PDF. Please try again.'}), 500