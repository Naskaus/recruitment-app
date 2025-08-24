# app/dispatch/routes.py

from flask import Blueprint, render_template, request, jsonify, abort, current_app
from flask_login import login_required, current_user
from app.models import db, StaffProfile, User, Assignment, Venue, Role
from datetime import datetime, date, timedelta

dispatch_bp = Blueprint('dispatch', __name__, template_folder='../templates', url_prefix='/dispatch')

# --- Constants ---
CONTRACT_TYPES = {"1jour": 1, "10jours": 10, "1mois": 30}

# --- Helper function ---
def compute_end_date(start_date: date, contract_type: str) -> date:
    days = CONTRACT_TYPES.get(contract_type)
    if not days:
        raise ValueError("Invalid contract_type")
    return start_date + timedelta(days=days - 1)

# --- VIEWS (HTML PAGE) ---
@dispatch_bp.route('/')
@login_required
def dispatch_board():
    if not current_user.agency_id:
        abort(403, "User not associated with an agency.")

    agency_id = current_user.agency_id
    
    all_staff = StaffProfile.query.filter_by(agency_id=agency_id).order_by(StaffProfile.nickname).all()
    venues = Venue.query.filter_by(agency_id=agency_id).order_by(Venue.name).all()
    
    ongoing_assignments = {a.staff_id: a for a in Assignment.query.filter_by(agency_id=agency_id, status='ongoing')}

    available_staff = []
    dispatched_staff_map = {venue.name: [] for venue in venues}

    for s in all_staff:
        if s.id in ongoing_assignments:
            assignment = ongoing_assignments[s.id]
            if assignment.venue.name in dispatched_staff_map:
                dispatched_staff_map[assignment.venue.name].append(s)
        else:
            if s.status != 'Working':
                available_staff.append(s)

    return render_template('dispatch.html',
                           available_staff=available_staff,
                           dispatched_staff=dispatched_staff_map,
                           venues=venues)

# --- API (JSON ROUTES) ---
@dispatch_bp.route('/api/assignment/form-data')
@login_required
def get_assignment_form_data():
    """Provides necessary data to populate the assignment form dynamically."""
    if not current_user.agency_id:
        return jsonify({"status": "error", "message": "User not associated with an agency."}), 403

    try:
        agency_users = User.query.filter_by(agency_id=current_user.agency_id).order_by(User.username).all()
        managers = [{"id": user.id, "username": user.username} for user in agency_users]
        
        # --- FIX: Use updated static list for staff positions ---
        staff_positions = ["Dancer", "Hostess (P.R.)"]

        return jsonify({
            "status": "success",
            "roles": staff_positions, # This key is 'roles' for frontend JS compatibility
            "managers": managers
        })
    except Exception as e:
        current_app.logger.error(f"Error getting form data: {e}")
        return jsonify({"status": "error", "message": "Could not retrieve form data."}), 500

@dispatch_bp.route('/api/assignment', methods=['POST'])
@login_required
def create_assignment():
    if not current_user.agency_id:
        return jsonify({"status": "error", "message": "User not associated with an agency."}), 403

    data = request.get_json() or {}
    try:
        staff_id = int(data.get('staff_id'))
        venue_name = data.get('venue')
        role_name = data.get('role')
        contract_type = data.get('contract_type')
        start_date = datetime.fromisoformat(data.get('start_date')).date()
        base_salary = float(data.get('base_salary', 0))
        managed_by_user_id = int(data.get('managed_by_user_id'))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid payload. Check data types."}), 400
    
    agency_id = current_user.agency_id
    staff = StaffProfile.query.filter_by(id=staff_id, agency_id=agency_id).first()
    if not staff: return jsonify({"status": "error", "message": "Staff not found in your agency."}), 404
    
    venue = Venue.query.filter_by(name=venue_name, agency_id=agency_id).first()
    if not venue: 
        return jsonify({"status": "error", "message": "Venue not found in your agency."}), 404

    end_date = compute_end_date(start_date, contract_type)
    
    # Final clean version of the constructor
    new_a = Assignment(
        agency_id=agency_id,
        staff_id=staff_id,
        venue_id=venue.id,
        contract_role=role_name,
        contract_type=contract_type,
        start_date=start_date,
        end_date=end_date,
        base_salary=base_salary,
        status='ongoing',
        managed_by_user_id=managed_by_user_id
    )

    staff.status = 'Working'
    db.session.add(new_a)
    db.session.commit()
    return jsonify({"status": "success", "assignment": new_a.to_dict()}), 201


@dispatch_bp.route('/api/assignment/<int:assignment_id>/end', methods=['POST'])
@login_required
def end_assignment_now(assignment_id):
    a = Assignment.query.filter_by(id=assignment_id, agency_id=current_user.agency_id).first_or_404()
    if a.status != 'ongoing':
        return jsonify({"status": "error", "message": "Assignment is not ongoing."}), 400
    
    today = date.today()
    a.end_date = today if today >= a.start_date else a.start_date
    a.status = 'completed'
    
    if a.staff:
        other_ongoing = Assignment.query.filter(
            Assignment.staff_id == a.staff_id,
            Assignment.status == 'ongoing',
            Assignment.id != a.id,
            Assignment.agency_id == current_user.agency_id
        ).first()
        if not other_ongoing:
            a.staff.status = 'Active'

    db.session.commit()
    return jsonify({
        "status": "success", 
        "assignment": a.to_dict(),
        "contract_days": (a.end_date - a.start_date).days + 1
    }), 200

@dispatch_bp.route('/api/assignment/<int:assignment_id>', methods=['DELETE'])
@login_required
def delete_assignment(assignment_id):
    a = Assignment.query.filter_by(id=assignment_id, agency_id=current_user.agency_id).first_or_404()
    db.session.delete(a)
    db.session.commit()
    return jsonify({"status": "success"}), 200

@dispatch_bp.route('/api/assignment/<int:assignment_id>/finalize', methods=['POST'])
@login_required
def finalize_assignment(assignment_id):
    a = Assignment.query.filter_by(id=assignment_id, agency_id=current_user.agency_id).first_or_404()
    data = request.get_json() or {}
    final_status = data.get('status')

    if a.status not in ['ongoing', 'completed']:
        return jsonify({"status": "error", "message": f"Assignment cannot be finalized from its current state ({a.status})."}), 400
    if final_status != 'archived':
        return jsonify({"status": "error", "message": "Invalid final status. Must be 'archived'."}), 400
    
    a.status = 'archived'
    
    if a.staff:
        other_ongoing = Assignment.query.filter(
            Assignment.staff_id == a.staff_id,
            Assignment.status == 'ongoing',
            Assignment.id != a.id,
            Assignment.agency_id == current_user.agency_id
        ).first()
        if not other_ongoing:
            a.staff.status = 'Active'
            
    db.session.commit()
    return jsonify({"status": "success", "message": f"Assignment finalized as {final_status}.", "assignment": a.to_dict()}), 200