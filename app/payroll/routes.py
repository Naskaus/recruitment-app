# app/payroll/routes.py

from flask import Blueprint, render_template, request, flash, Response, jsonify
from flask_login import login_required
from app.models import db, Assignment, StaffProfile, User, PerformanceRecord
from datetime import datetime, date, time as dt_time, timedelta
from weasyprint import HTML

payroll_bp = Blueprint('payroll', __name__, template_folder='../templates', url_prefix='/payroll')

# --- Constantes (à déplacer dans un fichier de config plus tard) ---
CONTRACT_TYPES = {"1jour": 1, "10jours": 10, "1mois": 30}
DRINK_STAFF_COMMISSION = 100
DRINK_BAR_PRICE = 120
VENUE_LIST = ["Red Dragon", "Mandarin", "Shark"] # Temporairement ici

# --- Fonctions utilitaires (à déplacer dans un fichier utils.py plus tard) ---
def calc_lateness_penalty(arrival_time):
    if not arrival_time:
        return 0
    cutoff = dt_time(19, 30)
    if arrival_time <= cutoff:
        return 0
    minutes = (datetime.combine(date.today(), arrival_time) - datetime.combine(date.today(), cutoff)).seconds // 60
    return minutes * 5

def _get_or_create_daily_record(assignment_id: int, ymd: date) -> 'PerformanceRecord':
    rec = PerformanceRecord.query.filter_by(assignment_id=assignment_id, record_date=ymd).first()
    if rec: return rec
    rec = PerformanceRecord(assignment_id=assignment_id, record_date=ymd)
    db.session.add(rec)
    db.session.commit()
    return rec


# --- Vues (Pages HTML) ---
@payroll_bp.route('/')
@login_required
def payroll_page():
    selected_venue = request.args.get('venue')
    selected_contract_type = request.args.get('contract_type')
    selected_status = request.args.get('status')
    search_nickname = request.args.get('nickname')
    selected_manager_id = request.args.get('manager_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    q = Assignment.query.options(
        db.joinedload(Assignment.staff), 
        db.joinedload(Assignment.manager), 
        db.subqueryload(Assignment.performance_records)
    )

    if selected_venue:
        q = q.filter(Assignment.venue == selected_venue)
    
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

    start_date, end_date = None, None
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
    
    rows = []
    for a in all_assignments:
        contract_stats = {
            "drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0
        }
        original_duration = CONTRACT_TYPES.get(a.contract_type, 1)
        base_daily_salary = (a.base_salary / original_duration) if original_duration > 0 else 0

        for record in a.performance_records:
            daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
            daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
            bar_revenue = ((record.drinks_sold or 0) * DRINK_BAR_PRICE) + (record.special_commissions or 0)
            daily_profit = bar_revenue - daily_salary
            
            contract_stats["drinks"] += record.drinks_sold or 0
            contract_stats["special_comm"] += record.special_commissions or 0
            contract_stats["salary"] += daily_salary
            contract_stats["commission"] += daily_commission
            contract_stats["profit"] += daily_profit

        rows.append({
            "assignment": a,
            "contract_days": (a.end_date - a.start_date).days + 1,
            "days_worked": len(a.performance_records),
            "original_duration": original_duration,
            "contract_stats": contract_stats
        })
        
    total_profit = sum(row['contract_stats']['profit'] for row in rows)
    total_days_worked = sum(row['days_worked'] for row in rows)

    summary_stats = {
        "total_profit": total_profit,
        "total_days_worked": total_days_worked
    }

    all_managers = User.query.order_by(User.username).all()

    filter_data = {
        "venues": VENUE_LIST,
        "contract_types": CONTRACT_TYPES.keys(),
        "statuses": ['ongoing', 'archived'],
        "managers": all_managers,
        "selected_venue": selected_venue,
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
    a = Assignment.query.get(assignment_id)
    if not a:
        return jsonify({"status": "error", "message": "Assignment not found."}), 404
    records = PerformanceRecord.query.filter_by(assignment_id=assignment_id) \
                                     .order_by(PerformanceRecord.record_date.desc()).all()
    original_days = CONTRACT_TYPES.get(a.contract_type)
    
    contract_data = {
        "start_date": a.start_date.isoformat(),
        "end_date": a.end_date.isoformat(),
        "base_salary": a.base_salary,
        "contract_days": (a.end_date - a.start_date).days + 1,
        "contract_type": a.contract_type,
        "original_days": original_days,
        "status": a.status
    }

    # --- START OF FINAL FIX ---
    # A contract is considered complete and ready for summary if the number of records
    # matches the total number of days in the contract.
    total_contract_days = (a.end_date - a.start_date).days + 1
    all_days_recorded = len(records) >= total_contract_days

    # Override status to 'completed' only if all performance records have been filled.
    if all_days_recorded and a.status == 'ongoing':
        contract_data['status'] = 'completed'
    # --- END OF FINAL FIX ---

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
    a = Assignment.query.get(assignment_id)
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
    rec.lateness_penalty = float(calc_lateness_penalty(rec.arrival_time))
    db.session.commit()
    return jsonify({"status": "success", "record": rec.to_dict()}), 200


# --- Génération de PDF ---

@payroll_bp.route('/pdf')
@login_required
def payroll_pdf():
    selected_venue = request.args.get('venue')
    selected_contract_type = request.args.get('contract_type')
    selected_status = request.args.get('status')
    search_nickname = request.args.get('nickname')
    selected_manager_id = request.args.get('manager_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    q = Assignment.query.options(
        db.joinedload(Assignment.staff), 
        db.joinedload(Assignment.manager), 
        db.subqueryload(Assignment.performance_records)
    )

    if selected_venue: q = q.filter(Assignment.venue == selected_venue)
    if selected_contract_type: q = q.filter(Assignment.contract_type == selected_contract_type)
    if selected_status: q = q.filter(Assignment.status == selected_status)
    else: q = q.filter(Assignment.status.in_(['ongoing', 'archived']))
    if search_nickname: q = q.join(StaffProfile).filter(StaffProfile.nickname.ilike(f'%{search_nickname}%'))
    if selected_manager_id: q = q.filter(Assignment.managed_by_user_id == selected_manager_id)

    start_date, end_date = None, None
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        q = q.filter(Assignment.end_date >= start_date)
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        q = q.filter(Assignment.start_date <= end_date)

    status_order = db.case((Assignment.status == 'ongoing', 1), (Assignment.status == 'archived', 2), else_=3).label("status_order")
    all_assignments = q.order_by(status_order, Assignment.start_date.asc()).all()

    rows = []
    for a in all_assignments:
        contract_stats = { "drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0 }
        original_duration = CONTRACT_TYPES.get(a.contract_type, 1)
        base_daily_salary = (a.base_salary / original_duration) if original_duration > 0 else 0
        for record in a.performance_records:
            daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
            daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
            bar_revenue = ((record.drinks_sold or 0) * DRINK_BAR_PRICE) + (record.special_commissions or 0)
            daily_profit = bar_revenue - daily_salary
            contract_stats["drinks"] += record.drinks_sold or 0
            contract_stats["special_comm"] += record.special_commissions or 0
            contract_stats["salary"] += daily_salary
            contract_stats["commission"] += daily_commission
            contract_stats["profit"] += daily_profit
        rows.append({
            "assignment": a, "contract_days": (a.end_date - a.start_date).days + 1,
            "days_worked": len(a.performance_records), "original_duration": original_duration,
            "contract_stats": contract_stats
        })

    total_profit = sum(row['contract_stats']['profit'] for row in rows)
    total_days_worked = sum(row['days_worked'] for row in rows)
    summary_stats = { "total_profit": total_profit, "total_days_worked": total_days_worked }

    manager_name = None
    if selected_manager_id:
        manager = User.query.get(selected_manager_id)
        if manager:
            manager_name = manager.username

    filter_data = {
        "selected_venue": selected_venue, 
        "selected_contract_type": selected_contract_type,
        "selected_status": selected_status, 
        "search_nickname": search_nickname,
        "selected_manager_name": manager_name,
        "selected_start_date": start_date_str, 
        "selected_end_date": end_date_str
    }

    html_for_pdf = render_template('payroll_pdf.html', 
                                   assignments=rows, 
                                   summary=summary_stats,
                                   filters=filter_data,
                                   report_date=date.today())

    pdf = HTML(string=html_for_pdf).write_pdf()

    return Response(pdf,
                  mimetype='application/pdf',
                  headers={'Content-Disposition': 'attachment; filename=payroll_report.pdf'})

@payroll_bp.route('/assignment/<int:assignment_id>/pdf')
@login_required
def assignment_pdf(assignment_id):
    assignment = Assignment.query.options(
        db.joinedload(Assignment.staff),
        db.joinedload(Assignment.manager),
        db.subqueryload(Assignment.performance_records)
    ).get_or_404(assignment_id)

    contract_stats = { "drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0 }
    original_duration = CONTRACT_TYPES.get(assignment.contract_type, 1)
    base_daily_salary = (assignment.base_salary / original_duration) if original_duration > 0 else 0

    for record in assignment.performance_records:
        daily_salary = (base_daily_salary + (record.bonus or 0) - (record.malus or 0) - (record.lateness_penalty or 0))
        daily_commission = (record.drinks_sold or 0) * DRINK_STAFF_COMMISSION
        bar_revenue = ((record.drinks_sold or 0) * DRINK_BAR_PRICE) + (record.special_commissions or 0)
        daily_profit = bar_revenue - daily_salary

        contract_stats["drinks"] += record.drinks_sold or 0
        contract_stats["special_comm"] += record.special_commissions or 0
        contract_stats["salary"] += daily_salary
        contract_stats["commission"] += daily_commission
        contract_stats["profit"] += daily_profit

    rows = [{
        "assignment": assignment,
        "contract_days": (assignment.end_date - assignment.start_date).days + 1,
        "days_worked": len(assignment.performance_records),
        "original_duration": original_duration,
        "contract_stats": contract_stats
    }]

    summary_stats = {
        "total_profit": contract_stats["profit"],
        "total_days_worked": len(assignment.performance_records)
    }

    html_for_pdf = render_template('assignment_pdf.html',
                                   assignments=rows,
                                   summary=summary_stats,
                                   contract_stats=contract_stats,
                                   filters={},
                                   report_date=date.today())

    pdf = HTML(string=html_for_pdf).write_pdf()

    staff_name = assignment.staff.nickname if assignment.staff else assignment.archived_staff_name
    filename = f"report_{staff_name}_{assignment.start_date.strftime('%Y-%m-%d')}.pdf"

    return Response(pdf,
                  mimetype='application/pdf',
                  headers={'Content-Disposition': f'attachment; filename={filename}'})