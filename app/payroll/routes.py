# app/payroll/routes.py

from flask import Blueprint, render_template, request, flash, Response, jsonify, abort, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.models import db, Assignment, StaffProfile, User, PerformanceRecord, Venue, AgencyContract, ContractCalculations
from app.services.payroll_service import update_or_create_contract_calculations
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
    
    # Process rows for display and calculation using payroll service
    rows = []
    total_profit = 0
    total_days_worked = 0
    
    for a in all_assignments:
        # Update or create contract calculations using the payroll service
        try:
            contract_calc = update_or_create_contract_calculations(a.id)
        except Exception as e:
            current_app.logger.error(f"Error calculating contract {a.id}: {str(e)}")
            # Fallback to empty calculations if service fails
            contract_calc = None
        
        # Get contract duration from AgencyContract table
        contract = AgencyContract.query.filter_by(name=a.contract_type, agency_id=agency_id).first()
        original_duration = contract.days if contract else 1
        
        # Use calculated values from ContractCalculations table
        if contract_calc:
            contract_stats = {
                "drinks": contract_calc.total_drinks,
                "special_comm": contract_calc.total_special_comm,
                "salary": contract_calc.total_salary,
                "commission": contract_calc.total_commission,
                "profit": contract_calc.total_profit
            }
            days_worked = contract_calc.days_worked
        else:
            # Fallback to manual calculation if service failed
            contract_stats = {"drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0}
            days_worked = len(a.performance_records)
        
        rows.append({
            "assignment": a,
            "days_worked": days_worked,
            "original_duration": original_duration,
            "contract_stats": contract_stats
        })
        total_profit += contract_stats["profit"]
        total_days_worked += days_worked

    summary_stats = {"total_profit": total_profit, "total_days_worked": total_days_worked}

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

    # Sauvegarder les données de base
    rec.arrival_time = time_or_none(data.get('arrival_time'))
    rec.departure_time = time_or_none(data.get('departure_time'))
    rec.drinks_sold = int(data.get('drinks_sold') or 0)
    rec.special_commissions = float(data.get('special_commissions') or 0.0)
    rec.bonus = float(data.get('bonus') or 0.0)
    rec.malus = float(data.get('malus') or 0.0)
    
    # Utiliser le service de paie pour calculer les valeurs automatiquement
    try:
        from app.services.payroll_service import calculate_lateness_penalty
        
        # Récupérer le contrat d'agence pour les règles de calcul
        agency_contract = AgencyContract.query.filter_by(
            name=a.contract_type,
            agency_id=agency_id
        ).first()
        
        # Calculer la pénalité de retard en utilisant le service
        lateness_penalty = calculate_lateness_penalty(rec, agency_contract) if agency_contract else 0.0
        rec.lateness_penalty = lateness_penalty
        
        # Calculer le salaire journalier
        # Récupérer la durée du contrat depuis AgencyContract
        contract_days = agency_contract.days if agency_contract else 1
        base_daily_salary = (a.base_salary / contract_days) if contract_days > 0 else 0
        
        # Salaire journalier = salaire de base + bonus - malus - pénalité de retard
        daily_salary = base_daily_salary + rec.bonus - rec.malus - lateness_penalty
        rec.daily_salary = daily_salary
        
        # Calculer le profit journalier
        # Revenus = (boissons * prix des boissons) + commissions spéciales
        drink_price = agency_contract.drink_price if agency_contract else 220  # Prix par défaut
        daily_revenue = (rec.drinks_sold * drink_price) + rec.special_commissions
        
        # Coûts = salaire journalier + commission sur les boissons
        staff_commission = agency_contract.staff_commission if agency_contract else 100  # Commission par défaut
        daily_commission = rec.drinks_sold * staff_commission
        daily_costs = daily_salary + daily_commission
        
        # Profit journalier = revenus - coûts
        daily_profit = daily_revenue - daily_costs
        rec.daily_profit = daily_profit
        
        current_app.logger.info(f"Calculs automatiques pour assignment {assignment_id}, date {ymd}:")
        current_app.logger.info(f"  - Pénalité de retard: {lateness_penalty}")
        current_app.logger.info(f"  - Salaire journalier: {daily_salary}")
        current_app.logger.info(f"  - Profit journalier: {daily_profit}")
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors du calcul automatique pour assignment {assignment_id}: {str(e)}")
        # Fallback aux calculs manuels en cas d'erreur
        rec.lateness_penalty = float(calc_lateness_penalty(rec.arrival_time, agency_id))
        rec.daily_salary = 0.0
        rec.daily_profit = 0.0
    
    db.session.commit()
    return jsonify({"status": "success", "record": rec.to_dict()}), 200


@payroll_bp.route('/api/performance/preview', methods=['POST'])
@login_required
def preview_performance():
    """
    Endpoint pour prévisualiser les calculs de performance sans sauvegarder.
    Utilise le service de paie pour calculer les valeurs en temps réel.
    """
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
        return jsonify({"status": "error", "message": "Performance can only be previewed for ongoing assignments."}), 400
    
    if not (a.start_date <= ymd <= a.end_date):
        return jsonify({"status": "error", "message": "Record date must be within contract period."}), 400

    # Créer un objet temporaire pour les calculs
    from app.models import PerformanceRecord
    temp_record = PerformanceRecord(
        assignment_id=assignment_id,
        record_date=ymd,
        arrival_time=datetime.strptime(data.get('arrival_time'), '%H:%M').time() if data.get('arrival_time') else None,
        departure_time=datetime.strptime(data.get('departure_time'), '%H:%M').time() if data.get('departure_time') else None,
        drinks_sold=int(data.get('drinks_sold', 0)),
        special_commissions=float(data.get('special_commissions', 0)),
        bonus=float(data.get('bonus', 0)),
        malus=float(data.get('malus', 0))
    )

    try:
        from app.services.payroll_service import calculate_lateness_penalty
        
        # Récupérer le contrat d'agence pour les règles de calcul
        agency_contract = AgencyContract.query.filter_by(
            name=a.contract_type,
            agency_id=agency_id
        ).first()
        
        # Calculer la pénalité de retard en utilisant le service
        lateness_penalty = calculate_lateness_penalty(temp_record, agency_contract) if agency_contract else 0.0
        
        # Calculer le salaire journalier
        contract_days = agency_contract.days if agency_contract else 1
        base_daily_salary = (a.base_salary / contract_days) if contract_days > 0 else 0
        
        # Salaire journalier = salaire de base + bonus - malus - pénalité de retard
        daily_salary = base_daily_salary + temp_record.bonus - temp_record.malus - lateness_penalty
        
        # Calculer le profit journalier
        drink_price = agency_contract.drink_price if agency_contract else 220
        daily_revenue = (temp_record.drinks_sold * drink_price) + temp_record.special_commissions
        
        staff_commission = agency_contract.staff_commission if agency_contract else 100
        daily_commission = temp_record.drinks_sold * staff_commission
        daily_costs = daily_salary + daily_commission
        
        daily_profit = daily_revenue - daily_costs
        
        # Calculer la commission payée
        commission_paid = daily_commission
        
        # Calculer le salaire de base proratisé
        prorated_base = base_daily_salary
        
        return jsonify({
            "status": "success",
            "lateness_penalty": lateness_penalty,
            "daily_salary": daily_salary,
            "daily_profit": daily_profit,
            "commission_paid": commission_paid,
            "prorated_base": prorated_base
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de la prévisualisation pour assignment {assignment_id}: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to calculate preview"}), 500

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
    
    # Process rows for display and calculation using ContractCalculations as single source of truth
    rows = []
    total_profit = 0
    total_days_worked = 0
    for a in all_assignments:
        # Get contract duration from AgencyContract table
        contract = AgencyContract.query.filter_by(name=a.contract_type, agency_id=agency_id).first()
        original_duration = contract.days if contract else 1
        
        # Use ContractCalculations as single source of truth
        try:
            from app.services.payroll_service import update_or_create_contract_calculations
            contract_calc = update_or_create_contract_calculations(a.id)
            
            contract_stats = {
                "drinks": contract_calc.total_drinks,
                "special_comm": contract_calc.total_special_comm,
                "salary": contract_calc.total_salary,
                "commission": contract_calc.total_commission,
                "profit": contract_calc.total_profit
            }
            days_worked = contract_calc.days_worked
        except Exception as e:
            current_app.logger.error(f"Error getting contract calculations for assignment {a.id}: {str(e)}")
            # Fallback to empty stats if service fails
            contract_stats = {"drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0}
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

    # Get contract duration from AgencyContract table
    contract = AgencyContract.query.filter_by(name=assignment.contract_type, agency_id=agency_id).first()
    original_duration = contract.days if contract else 1
    
    # Use ContractCalculations as single source of truth
    try:
        from app.services.payroll_service import update_or_create_contract_calculations
        contract_calc = update_or_create_contract_calculations(assignment_id)
        
        contract_stats = {
            "drinks": contract_calc.total_drinks,
            "special_comm": contract_calc.total_special_comm,
            "salary": contract_calc.total_salary,
            "commission": contract_calc.total_commission,
            "profit": contract_calc.total_profit
        }
        days_worked = contract_calc.days_worked
    except Exception as e:
        current_app.logger.error(f"Error getting contract calculations for PDF: {str(e)}")
        # Fallback to empty stats if service fails
        contract_stats = {"drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0}
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


# --- API ENDPOINTS ---
@payroll_bp.route('/api/assignment/<int:assignment_id>/summary')
@login_required
def assignment_summary_api(assignment_id):
    """
    API endpoint pour récupérer le résumé des calculs d'un contrat.
    Utilise le service de paie pour calculer les totaux en temps réel.
    """
    from flask import session
    
    # Get current agency ID
    if current_user.role_name == 'WebDev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    # Security: Ensure the assignment belongs to the user's agency
    assignment = Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).first()
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404
    
    try:
        # Utiliser le service de paie pour calculer les totaux
        from app.services.payroll_service import update_or_create_contract_calculations
        
        # Calculer et sauvegarder les totaux
        contract_calc = update_or_create_contract_calculations(assignment_id)
        
        # Retourner les données au format JSON
        return jsonify({
            'total_salary': contract_calc.total_salary,
            'total_commission': contract_calc.total_commission,
            'total_profit': contract_calc.total_profit,
            'days_worked': contract_calc.days_worked,
            'total_drinks': contract_calc.total_drinks,
            'total_special_comm': contract_calc.total_special_comm,
            'last_updated': contract_calc.last_updated.isoformat() if contract_calc.last_updated else None
        })
        
    except Exception as e:
        current_app.logger.error(f"Error calculating contract summary for assignment {assignment_id}: {e}")
        return jsonify({'error': 'Failed to calculate contract summary'}), 500