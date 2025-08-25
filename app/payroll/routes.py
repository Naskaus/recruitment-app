# app/payroll/routes.py

from flask import Blueprint, render_template, request, flash, Response, jsonify, abort, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.models import db, Assignment, StaffProfile, User, PerformanceRecord, Venue, AgencyContract
from datetime import datetime, date, time as dt_time, timedelta
from weasyprint import HTML

payroll_bp = Blueprint('payroll', __name__, template_folder='../templates', url_prefix='/payroll')

# --- Constants ---
CONTRACT_TYPES = {"1jour": 1, "10jours": 10, "1mois": 30}
DRINK_STAFF_COMMISSION = 100
DRINK_BAR_PRICE = 220
BAR_COMMISSION = DRINK_BAR_PRICE - DRINK_STAFF_COMMISSION  # 220 - 100 = 120 THB per drink

# --- Helper Functions ---
def calc_lateness_penalty(arrival_time, agency_id):
    if not arrival_time:
        return 0
    
    # Get contract rules from AgencyContract
    # Get the first contract to use its rules (they should be the same for all contracts in an agency)
    contract = AgencyContract.query.filter_by(agency_id=agency_id).first()
    if not contract:
        # Fallback to default values
        cutoff_time = dt_time(19, 30)
        first_minute_penalty = 0
        additional_minute_penalty = 5
    else:
        # Parse cutoff time from string (format: "19:30")
        hour, minute = map(int, contract.late_cutoff_time.split(':'))
        cutoff_time = dt_time(hour, minute)
        first_minute_penalty = contract.first_minute_penalty
        additional_minute_penalty = contract.additional_minute_penalty
    
    if arrival_time <= cutoff_time:
        return 0
    
    minutes_late = (datetime.combine(date.today(), arrival_time) - datetime.combine(date.today(), cutoff_time)).seconds // 60
    
    if minutes_late == 0:
        return 0
    elif minutes_late == 1:
        return first_minute_penalty
    else:
        # First minute penalty + additional minutes penalty
        return first_minute_penalty + (minutes_late - 1) * additional_minute_penalty

def _get_or_create_daily_record(assignment_id: int, ymd: date) -> 'PerformanceRecord':
    rec = PerformanceRecord.query.filter_by(assignment_id=assignment_id, record_date=ymd).first()
    if rec: return rec
    rec = PerformanceRecord(assignment_id=assignment_id, record_date=ymd)
    db.session.add(rec)
    db.session.commit()
    return rec


# --- VIEWS (HTML PAGES) ---
@payroll_bp.route('/')
@login_required
def payroll_page():
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        abort(403, "User not associated with an agency.")

    # Get filter arguments from request
    selected_venue_id = request.args.get('venue_id', type=int)
    selected_contract_type = request.args.get('contract_type')
    selected_status = request.args.get('status')
    search_nickname = request.args.get('nickname')
    selected_manager_id = request.args.get('manager_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Base query scoped to the user's agency
    q = Assignment.query.filter_by(agency_id=agency_id).options(
        db.joinedload(Assignment.staff), 
        db.joinedload(Assignment.manager), 
        db.joinedload(Assignment.venue),
        db.subqueryload(Assignment.performance_records)
    )

    # Apply filters
    if selected_venue_id:
        q = q.filter(Assignment.venue_id == selected_venue_id)
    if selected_contract_type:
        q = q.filter(Assignment.contract_type == selected_contract_type)
    if selected_status:
        q = q.filter(Assignment.status == selected_status)
    else:
        q = q.filter(Assignment.status.in_(['ongoing', 'archived']))
    if search_nickname:
        q = q.join(StaffProfile).filter(StaffProfile.nickname.ilike(f'%{search_nickname}%'))
    if selected_manager_id:
        q = q.filter(Assignment.managed_by_user_id == selected_manager_id)

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            q = q.filter(Assignment.end_date >= start_date)
        except ValueError:
            flash(f'Invalid start date format: {start_date_str}. Please use YYYY-MM-DD.', 'danger')
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            q = q.filter(Assignment.start_date <= end_date)
        except ValueError:
            flash(f'Invalid end date format: {end_date_str}. Please use YYYY-MM-DD.', 'danger')
    
    status_order = db.case((Assignment.status == 'ongoing', 1), (Assignment.status == 'archived', 2), else_=3).label("status_order")
    all_assignments = q.order_by(status_order, Assignment.start_date.asc()).all()
    
    # Process rows for display and calculation
    rows = []
    total_profit = 0
    total_days_worked = 0
    for a in all_assignments:
        contract_stats = { "drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0 }
        
        # Get contract duration from AgencyContract table
        contract = AgencyContract.query.filter_by(name=a.contract_type, agency_id=agency_id).first()
        original_duration = contract.days if contract else 1
        base_daily_salary = (a.base_salary / original_duration) if original_duration > 0 else 0

        for record in a.performance_records:
            daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
            daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
            bar_revenue = ((record.drinks_sold or 0) * BAR_COMMISSION) + (record.special_commissions or 0)
            daily_profit = bar_revenue - daily_salary
            
            contract_stats["profit"] += daily_profit
        
        days_worked = len(a.performance_records)
        rows.append({
            "assignment": a,
            "days_worked": days_worked,
            "original_duration": original_duration, # <-- FIX: Re-added this line
            "contract_stats": contract_stats
        })
        total_profit += contract_stats["profit"]
        total_days_worked += days_worked

    summary_stats = { "total_profit": total_profit, "total_days_worked": total_days_worked }

    # Fetch dynamic filter data, scoped to the agency
    agency_managers = User.query.filter_by(agency_id=agency_id).order_by(User.username).all()
    agency_venues = Venue.query.filter_by(agency_id=agency_id).order_by(Venue.name).all()

    filter_data = {
        "venues": agency_venues,
        "contract_types": CONTRACT_TYPES.keys(),
        "statuses": ['ongoing', 'archived'],
        "managers": agency_managers,
        "selected_venue_id": selected_venue_id,
        "selected_contract_type": selected_contract_type,
        "selected_status": selected_status,
        "search_nickname": search_nickname,
        "selected_manager_id": selected_manager_id,
        "selected_start_date": start_date_str,
        "selected_end_date": end_date_str
    }

    return render_template('payroll.html', assignments=rows, filters=filter_data, summary=summary_stats)

# --- API Performance ---

@payroll_bp.route('/api/performance/<int:assignment_id>/<string:ymd>', methods=['GET'])
@login_required
def get_performance(assignment_id, ymd):
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    # Security: Ensure the requested assignment belongs to the user's agency
    Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).first_or_404()
    
    try:
        day = datetime.fromisoformat(ymd).date()
    except Exception:
        return jsonify({"status": "error", "message": "Invalid date."}), 400
    rec = PerformanceRecord.query.filter_by(assignment_id=assignment_id, record_date=day).first()
    if not rec:
        return jsonify({"status": "success", "record": None}), 200
    return jsonify({"status": "success", "record": rec.to_dict()}), 200

@payroll_bp.route('/api/performance/<int:assignment_id>', methods=['GET'])
@login_required
def list_performance_for_assignment(assignment_id):
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    a = Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).first_or_404()
    
    records = PerformanceRecord.query.filter_by(assignment_id=assignment_id) \
                                     .order_by(PerformanceRecord.record_date.desc()).all()
    
    # Get contract rules for penalty calculation
    contract = AgencyContract.query.filter_by(name=a.contract_type, agency_id=agency_id).first()
    
    # Debug: Log contract lookup
    current_app.logger.info(f"Looking for contract: name='{a.contract_type}', agency_id={agency_id}")
    current_app.logger.info(f"Found contract: {contract}")
    if contract:
        current_app.logger.info(f"Contract rules: first_minute_penalty={contract.first_minute_penalty}, additional_minute_penalty={contract.additional_minute_penalty}")
    
    contract_rules = {
        "late_cutoff_time": contract.late_cutoff_time if contract else "19:30",
        "first_minute_penalty": contract.first_minute_penalty if contract else 0,
        "additional_minute_penalty": contract.additional_minute_penalty if contract else 5
    } if contract else {
        "late_cutoff_time": "19:30",
        "first_minute_penalty": 0,
        "additional_minute_penalty": 5
    }
    
    contract_data = {
        "start_date": a.start_date.isoformat(),
        "end_date": a.end_date.isoformat(),
        "base_salary": a.base_salary,
        "contract_type": a.contract_type,
        "status": a.status,
        "contract_rules": contract_rules
    }

    return jsonify({
        "status": "success",
        "records": [r.to_dict() for r in records],
        "contract": contract_data
    }), 200

@payroll_bp.route('/api/performance', methods=['POST'])
@login_required
def upsert_performance():
    data = request.get_json() or {}
    try:
        assignment_id = int(data.get('assignment_id'))
        ymd = datetime.fromisoformat(data.get('record_date')).date()
    except Exception:
        return jsonify({"status": "error", "message": "Invalid assignment_id or record_date"}), 400

    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    a = Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).first()
    if not a or a.status != 'ongoing':
        return jsonify({"status": "error", "message": "Performance can only be added to ongoing assignments."}), 400
    if not (a.start_date <= ymd <= a.end_date):
        return jsonify({"status": "error", "message": "Date outside contract period."}), 400
    
    rec = _get_or_create_daily_record(assignment_id, ymd)
    def time_or_none(s):
        if not s: return None
        try: return dt_time.fromisoformat(s)
        except Exception: return None

    rec.arrival_time = time_or_none(data.get('arrival_time'))
    rec.departure_time = time_or_none(data.get('departure_time'))
    rec.drinks_sold = int(data.get('drinks_sold') or 0)
    rec.special_commissions = float(data.get('special_commissions') or 0.0)
    rec.bonus = float(data.get('bonus') or 0.0)
    rec.malus = float(data.get('malus') or 0.0)
    rec.lateness_penalty = float(calc_lateness_penalty(rec.arrival_time, agency_id))
    db.session.commit()
    return jsonify({"status": "success", "record": rec.to_dict()}), 200

# --- PDF Generation ---

# Note: The 'payroll_pdf' route for the entire list is complex and less common.
# It's kept for now but might be revised or removed in favor of more specific reports.
@payroll_bp.route('/pdf')
@login_required
def payroll_pdf():
    """Generates a PDF report for the filtered payroll data."""
    from flask import session
    
    current_app.logger.info("PDF generation started")
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        current_app.logger.error("User not associated with an agency")
        abort(403, "User not associated with an agency.")
    current_app.logger.info(f"Processing PDF for agency_id: {agency_id}")

    # Get filter arguments from request (same as payroll_page)
    selected_venue_id = request.args.get('venue_id', type=int)
    selected_contract_type = request.args.get('contract_type')
    selected_status = request.args.get('status')
    search_nickname = request.args.get('nickname')
    selected_manager_id = request.args.get('manager_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Base query scoped to the user's agency
    q = Assignment.query.filter_by(agency_id=agency_id).options(
        db.joinedload(Assignment.staff), 
        db.joinedload(Assignment.manager), 
        db.joinedload(Assignment.venue),
        db.subqueryload(Assignment.performance_records)
    )

    # Apply filters (same logic as payroll_page)
    if selected_venue_id:
        q = q.filter(Assignment.venue_id == selected_venue_id)
    if selected_contract_type:
        q = q.filter(Assignment.contract_type == selected_contract_type)
    if selected_status:
        q = q.filter(Assignment.status == selected_status)
    else:
        q = q.filter(Assignment.status.in_(['ongoing', 'archived']))
    if search_nickname:
        q = q.join(StaffProfile).filter(StaffProfile.nickname.ilike(f'%{search_nickname}%'))
    if selected_manager_id:
        q = q.filter(Assignment.managed_by_user_id == selected_manager_id)

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            q = q.filter(Assignment.end_date >= start_date)
        except ValueError:
            pass
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            q = q.filter(Assignment.start_date <= end_date)
        except ValueError:
            pass
    
    status_order = db.case((Assignment.status == 'ongoing', 1), (Assignment.status == 'archived', 2), else_=3).label("status_order")
    all_assignments = q.order_by(status_order, Assignment.start_date.asc()).all()
    
    # Process rows for display and calculation (same as payroll_page)
    rows = []
    total_profit = 0
    total_days_worked = 0
    for a in all_assignments:
        contract_stats = { "drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0 }
        
        # Get contract duration from AgencyContract table
        contract = AgencyContract.query.filter_by(name=a.contract_type, agency_id=agency_id).first()
        original_duration = contract.days if contract else 1
        base_daily_salary = (a.base_salary / original_duration) if original_duration > 0 else 0

        for record in a.performance_records:
            daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
            daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
            bar_revenue = ((record.drinks_sold or 0) * BAR_COMMISSION) + (record.special_commissions or 0)
            daily_profit = bar_revenue - daily_salary
            
            contract_stats["drinks"] += record.drinks_sold or 0
            contract_stats["special_comm"] += record.special_commissions or 0
            contract_stats["salary"] += daily_salary
            contract_stats["commission"] += daily_commission
            contract_stats["profit"] += daily_profit
        
        days_worked = len(a.performance_records)
        rows.append({
            "assignment": a,
            "days_worked": days_worked,
            "original_duration": original_duration,
            "contract_stats": contract_stats
        })
        total_profit += contract_stats["profit"]
        total_days_worked += days_worked

    summary_stats = { "total_profit": total_profit, "total_days_worked": total_days_worked }

    try:
        current_app.logger.info(f"Rendering PDF template with {len(rows)} assignments")
        html_for_pdf = render_template('Payroll_pdf.html',
                                       assignments=rows,
                                       summary=summary_stats,
                                       filters=request.args,
                                       report_date=date.today())

        current_app.logger.info("Generating PDF from HTML")
        pdf = HTML(string=html_for_pdf).write_pdf()
        filename = f"payroll_report_{date.today().strftime('%Y-%m-%d')}.pdf"

        current_app.logger.info(f"PDF generated successfully, size: {len(pdf)} bytes")
        response = Response(pdf, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.headers['Content-Length'] = len(pdf)
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error generating payroll PDF: {e}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': 'Failed to generate PDF. Please try again.'}), 500


@payroll_bp.route('/assignment/<int:assignment_id>/pdf')
@login_required
def assignment_pdf(assignment_id):
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    # Security: Ensure the assignment belongs to the user's agency
    assignment = Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).options(
        db.joinedload(Assignment.staff),
        db.joinedload(Assignment.manager),
        db.joinedload(Assignment.venue),
        db.subqueryload(Assignment.performance_records)
    ).first_or_404()

    contract_stats = { "drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0 }
    
    # Get contract duration from AgencyContract table
    contract = AgencyContract.query.filter_by(name=assignment.contract_type, agency_id=agency_id).first()
    original_duration = contract.days if contract else 1
    base_daily_salary = (assignment.base_salary / original_duration) if original_duration > 0 else 0

    for record in assignment.performance_records:
        daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
        daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
        bar_revenue = ((record.drinks_sold or 0) * BAR_COMMISSION) + (record.special_commissions or 0)
        daily_profit = bar_revenue - daily_salary

        contract_stats["drinks"] += record.drinks_sold or 0
        contract_stats["special_comm"] += record.special_commissions or 0
        contract_stats["salary"] += daily_salary
        contract_stats["commission"] += daily_commission
        contract_stats["profit"] += daily_profit
    
    days_worked = len(assignment.performance_records)
    
    try:
        html_for_pdf = render_template('assignment_pdf.html',
                                       assignments=[{'assignment': assignment, 'days_worked': days_worked, 'original_duration': original_duration}],
                                       contract_stats=contract_stats,
                                       report_date=date.today(),
                                       timedelta=timedelta)

        pdf = HTML(string=html_for_pdf).write_pdf()

        staff_name = assignment.staff.nickname if assignment.staff else assignment.archived_staff_name
        filename = f"report_{staff_name}_{assignment.start_date.strftime('%Y-%m-%d')}.pdf"

        response = Response(pdf, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.headers['Content-Length'] = len(pdf)
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error generating assignment PDF for assignment {assignment_id}: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to generate PDF. Please try again.'}), 500