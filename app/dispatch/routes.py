# app/dispatch/routes.py

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app.models import db, StaffProfile, User, Assignment
from datetime import datetime, date, timedelta

dispatch_bp = Blueprint('dispatch', __name__, template_folder='../templates', url_prefix='/dispatch')

# --- Constantes (à déplacer dans un fichier de config plus tard) ---
VENUE_LIST = ["Red Dragon", "Mandarin", "Shark"]
ROLE_LIST = ["Dancer", "Hostess"]
STATUS_LIST = ["Active", "Working", "Quiet"]
CONTRACT_TYPES = {"1jour": 1, "10jours": 10, "1mois": 30}

# --- Fonction utilitaire (à déplacer dans un fichier utils.py plus tard) ---
def compute_end_date(start_date: date, contract_type: str) -> date:
    days = CONTRACT_TYPES.get(contract_type)
    if not days:
        raise ValueError("Invalid contract_type")
    return start_date + timedelta(days=days - 1)

# --- Vues (Page HTML) ---
@dispatch_bp.route('/')
@login_required
def dispatch_board():
    all_staff = StaffProfile.query.order_by(StaffProfile.nickname).all()
    # Eager load current assignments to avoid N+1 queries in the template
    ongoing_assignments = {a.staff_id: a for a in Assignment.query.filter_by(status='ongoing')}

    available_staff = []
    dispatched_staff_map = {venue: [] for venue in VENUE_LIST}

    for s in all_staff:
        if s.id in ongoing_assignments:
            assignment = ongoing_assignments[s.id]
            s.current_assignment = assignment # Attach for easy access in template
            if assignment.venue in dispatched_staff_map:
                dispatched_staff_map[assignment.venue].append(s)
        else:
            s.current_assignment = None
            if s.status != 'Working': # Safety check
                 available_staff.append(s)

    return render_template('dispatch.html',
                           available_staff=available_staff,
                           dispatched_staff=dispatched_staff_map,
                           venues=VENUE_LIST,
                           roles=ROLE_LIST,
                           users=User.query.order_by(User.username).all(),
                           statuses=STATUS_LIST)

# --- API (Routes JSON pour les contrats) ---
@dispatch_bp.route('/api/assignment/form-data')
@login_required
def get_assignment_form_data():
    """Provides necessary data to populate the assignment form dynamically."""
    try:
        all_users = User.query.order_by(User.username).all()
        managers = [{"id": user.id, "username": user.username} for user in all_users]
        
        return jsonify({
            "status": "success",
            "roles": ROLE_LIST,
            "managers": managers
        })
    except Exception as e:
        return jsonify({"status": "error", "message": "Could not retrieve form data."}), 500

@dispatch_bp.route('/api/assignment', methods=['POST'])
@login_required
def create_assignment():
    data = request.get_json() or {}
    try:
        staff_id = int(data.get('staff_id'))
        venue = data.get('venue')
        role = data.get('role')
        contract_type = data.get('contract_type')
        start_date = datetime.fromisoformat(data.get('start_date')).date()
        base_salary = float(data.get('base_salary', 0))
        managed_by_user_id = int(data.get('managed_by_user_id'))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid payload. Check data types."}), 400
    
    staff = StaffProfile.query.get(staff_id)
    if not staff: return jsonify({"status": "error", "message": "Staff not found."}), 404
    
    # --- LOGIC RULE: When dispatched, status becomes 'Working' ---
    staff.status = 'Working'
    
    overlapping = Assignment.query.filter(
        Assignment.staff_id == staff_id, 
        Assignment.status == 'ongoing', 
        Assignment.end_date >= start_date
    ).first()
    if overlapping: 
        return jsonify({"status": "error", "message": f"Staff already has an ongoing contract until {overlapping.end_date}."}), 409
    
    end_date = compute_end_date(start_date, contract_type)
    new_a = Assignment(
        staff_id=staff_id, 
        venue=venue, 
        role=role, 
        contract_type=contract_type, 
        start_date=start_date, 
        end_date=end_date, 
        base_salary=base_salary, 
        status='ongoing',
        managed_by_user_id=managed_by_user_id
    )
    db.session.add(new_a)
    db.session.commit()
    return jsonify({"status": "success", "assignment": new_a.to_dict()}), 201

@dispatch_bp.route('/api/assignment/<int:assignment_id>/end', methods=['POST'])
@login_required
def end_assignment_now(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    if a.status != 'ongoing':
        return jsonify({"status": "error", "message": "Assignment is not ongoing."}), 400
    
    today = date.today()
    a.end_date = today if today >= a.start_date else a.start_date
    a.status = 'completed'
    
    # --- LOGIC RULE: When contract ends, status becomes 'Active' if no other contracts are ongoing ---
    if a.staff:
        other_ongoing = Assignment.query.filter(
            Assignment.staff_id == a.staff_id,
            Assignment.status == 'ongoing',
            Assignment.id != a.id
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
    a = Assignment.query.get_or_404(assignment_id)
    if a.staff:
        a.staff.current_venue = None # Legacy, should be removed later
    db.session.delete(a)
    db.session.commit()
    return jsonify({"status": "success"}), 200

@dispatch_bp.route('/api/assignment/<int:assignment_id>/finalize', methods=['POST'])
@login_required
def finalize_assignment(assignment_id):
    a = Assignment.query.get_or_404(assignment_id)
    data = request.get_json() or {}
    final_status = data.get('status')

    if a.status not in ['ongoing', 'completed']:
        return jsonify({"status": "error", "message": f"Assignment cannot be finalized from its current state ({a.status})."}), 400
    if final_status != 'archived':
        return jsonify({"status": "error", "message": "Invalid final status. Must be 'archived'."}), 400
    
    a.status = 'archived'
    
    # --- LOGIC RULE: When contract is archived, status becomes 'Active' if no other contracts are ongoing ---
    if a.staff:
        other_ongoing = Assignment.query.filter(
            Assignment.staff_id == a.staff_id,
            Assignment.status == 'ongoing',
            Assignment.id != a.id
        ).first()
        if not other_ongoing:
            a.staff.status = 'Active'
            
    db.session.commit()
    return jsonify({"status": "success", "message": f"Assignment finalized as {final_status}.", "assignment": a.to_dict()}), 200
