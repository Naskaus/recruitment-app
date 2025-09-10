# app/payroll/routes.py

import time
from flask import Blueprint, render_template, request, flash, Response, jsonify, abort, redirect, url_for, current_app, session, make_response
from flask_login import login_required, current_user
from app.models import db, Assignment, StaffProfile, User, PerformanceRecord, Venue, AgencyContract, ContractCalculations
from app.services.payroll_service import update_or_create_contract_calculations, process_assignments_batch
from app.decorators import admin_required, manager_required, super_admin_required, webdev_required, payroll_view_required
from datetime import datetime, date, time as dt_time, timedelta
from weasyprint import HTML
from sqlalchemy.orm import joinedload

payroll_bp = Blueprint('payroll', __name__, template_folder='../templates', url_prefix='/payroll')

# --- Constants ---

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
@payroll_view_required
def payroll_page():
    """
    Page principale de la paie avec filtrage par défaut optimisé.
    
    PERFORMANCE: Par défaut, ne charge que les assignments 'active' pour améliorer
    significativement les temps de chargement. Utilisez ?status=all pour voir tous les statuts.
    """
    from flask import session
    
    # Début du chronométrage
    start_time = time.time()
    current_app.logger.info(f"[PERF] Starting payroll page load - {datetime.now()}")
    
    # Get current agency ID
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        abort(403, "User not associated with an agency.")

    # Get filter arguments from request
    selected_venue_id = request.args.get('venue_id', type=int)
    selected_contract_type = request.args.get('contract_type')
    selected_status = request.args.get('status', 'active')  # Default to 'active' for better performance
    search_nickname = request.args.get('nickname')
    selected_manager_id = request.args.get('manager_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Base query scoped to the user's agency with eager loading to prevent N+1 queries
    q = Assignment.query.filter_by(agency_id=agency_id).options(
        joinedload(Assignment.staff),
        joinedload(Assignment.venue),
        joinedload(Assignment.contract_calculations),
        joinedload(Assignment.performance_records)
    )

    # Apply filters
    if selected_venue_id:
        q = q.filter(Assignment.venue_id == selected_venue_id)
    if selected_contract_type and selected_contract_type != 'all':
        q = q.filter(Assignment.contract_type == selected_contract_type)
    
    # Apply status filter with default to 'active' for better performance
    if selected_status and selected_status != 'all':
        q = q.filter(Assignment.status == selected_status)
    # Note: If status is 'all' or not provided, no status filter is applied (shows all statuses)
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
    
    status_order = db.case((Assignment.status == 'active', 1), (Assignment.status == 'ended', 2), (Assignment.status == 'archived', 3), else_=4).label("status_order")
    all_assignments = q.order_by(status_order, Assignment.start_date.asc()).all()
    
    # Log après récupération des assignments
    current_app.logger.info(f"[PERF] Assignments retrieved: {len(all_assignments)} in {(time.time() - start_time):.3f}s")
    
    # Process rows for display and calculation using optimized batch service
    rows = []
    total_profit = 0
    total_days_worked = 0
    
    # Début du traitement des calculs en lot
    calc_start_time = time.time()
    current_app.logger.info(f"[PERF] Starting batch processing for {len(all_assignments)} assignments")
    
    # OPTIMISATION: Traitement par lots au lieu de boucle individuelle
    try:
        batch_results = process_assignments_batch(all_assignments)
        current_app.logger.info(f"[PERF] Batch finished in {(time.time() - calc_start_time):.3f}s")
    except Exception as e:
        current_app.logger.error(f"Error in batch processing: {str(e)}")
        # Fallback to individual processing if batch fails
        batch_results = {}
        for a in all_assignments:
            try:
                contract_calc = update_or_create_contract_calculations(a.id)
                batch_results[a.id] = contract_calc
            except Exception as calc_e:
                current_app.logger.error(f"Error calculating contract {a.id}: {str(calc_e)}")
                batch_results[a.id] = None
    
    # PRÉ-REQUÊTE pour les contrats (éviter N requêtes dans la boucle)
    agency_contracts = AgencyContract.query.filter_by(agency_id=agency_id).all()
    contracts_dict = {contract.name: contract for contract in agency_contracts}
    
    # Construire les rows à partir des résultats batch
    for a in all_assignments:
        contract_calc = batch_results.get(a.id)
        
        # Get contract duration depuis le dictionnaire (pas de requête DB)
        contract = contracts_dict.get(a.contract_type)
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

    # Log après traitement des calculs
    current_app.logger.info(f"[PERF] Calculations finished in {(time.time() - calc_start_time):.3f}s")
    
    summary_stats = {"total_profit": total_profit, "total_days_worked": total_days_worked}

    # Fetch dynamic filter data, scoped to the agency
    agency_managers = User.query.filter_by(agency_id=agency_id).order_by(User.username).all()
    agency_venues = Venue.query.filter_by(agency_id=agency_id).order_by(Venue.name).all()

    agency_contracts_for_filter = AgencyContract.query.filter_by(agency_id=agency_id).order_by(AgencyContract.name).all()
    filter_data = {
        "venues": agency_venues,
        "contract_types": agency_contracts_for_filter,
        "statuses": ['ongoing', 'active', 'ended', 'archived', 'all'],
        "managers": agency_managers,
        "selected_venue_id": selected_venue_id,
        "selected_contract_type": selected_contract_type,
        "selected_status": selected_status,
        "search_nickname": search_nickname,
        "selected_manager_id": selected_manager_id,
        "selected_start_date": start_date_str,
        "selected_end_date": end_date_str
    }

    # Log final avant le rendu
    total_time = time.time() - start_time
    current_app.logger.info(f"[PERF] Payroll page ready to render in {total_time:.3f}s total (status filter: {selected_status})")
    
    return render_template('payroll.html', assignments=rows, filters=filter_data, summary=summary_stats, status_filter=selected_status)

# --- API Performance ---

@payroll_bp.route('/api/performance/<int:assignment_id>/<string:ymd>', methods=['GET'])
@login_required
@manager_required
def get_performance(assignment_id, ymd):
    from flask import session
    
    # Get current agency ID
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    # Security: Ensure the requested assignment belongs to the user's agency
    Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).options(
        joinedload(Assignment.staff),
        joinedload(Assignment.venue)
    ).first_or_404()
    
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
@manager_required
def list_performance_for_assignment(assignment_id):
    from flask import session
    
    # Get current agency ID
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    a = Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).options(
        joinedload(Assignment.staff),
        joinedload(Assignment.venue),
        joinedload(Assignment.contract_calculations)
    ).first_or_404()
    
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
@manager_required
def upsert_performance():
    data = request.get_json() or {}
    try:
        assignment_id = int(data.get('assignment_id'))
        ymd = datetime.fromisoformat(data.get('record_date')).date()
    except Exception:
        return jsonify({"status": "error", "message": "Invalid assignment_id or record_date"}), 400

    from flask import session
    
    # Get current agency ID
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    a = Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).options(
        joinedload(Assignment.staff),
        joinedload(Assignment.venue)
    ).first()
    if not a or a.status != 'active':
        return jsonify({"status": "error", "message": "Performance can only be added to active assignments."}), 400
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
@manager_required
def preview_performance():
    """
    Endpoint pour prévisualiser les calculs de performance sans sauvegarder.
    Utilise le service de paie pour calculer les valeurs en temps réel.
    """
    try:
        data = request.get_json() or {}
        
        # Validation des données reçues
        assignment_id = int(data.get('assignment_id'))
        ymd = datetime.fromisoformat(data.get('record_date')).date()
        
    except Exception as e:
        current_app.logger.error(f'API Validation Error: {e} - Data: {request.get_json(silent=True)}')
        return jsonify({'error': 'Invalid data provided', 'reason': str(e)}), 400

    from flask import session
    
    # Get current agency ID
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    a = Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).options(
        joinedload(Assignment.staff),
        joinedload(Assignment.venue)
    ).first()
    if not a or a.status != 'active':
        return jsonify({"status": "error", "message": "Performance can only be previewed for active assignments."}), 400
    
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

# --- Contract Summary API ---
@payroll_bp.route('/api/summary/<int:assignment_id>')
@login_required
@manager_required
def get_contract_summary(assignment_id):
    """
    Endpoint pour récupérer le résumé final d'un contrat terminé.
    Utilise le payroll_service pour récupérer les données calculées.
    """
    try:
        from flask import session
        
        # Get current agency ID
        if current_user.role == 'webdev':
            agency_id = session.get('current_agency_id', current_user.agency_id)
        else:
            agency_id = current_user.agency_id
        
        # Vérifier que l'assignment existe et appartient à l'agence
        assignment = Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).options(
            joinedload(Assignment.staff),
            joinedload(Assignment.venue),
            joinedload(Assignment.contract_calculations)
        ).first()
        if not assignment:
            return jsonify({"status": "error", "message": "Assignment not found"}), 404
        
        # Vérifier que le contrat est terminé
        if assignment.status not in ['ended', 'archived']:
            return jsonify({"status": "error", "message": "Summary only available for ended or archived contracts"}), 400
        
        # Récupérer les calculs finaux depuis ContractCalculations
        from app.models import ContractCalculations
        calculations = ContractCalculations.query.filter_by(assignment_id=assignment_id).first()
        
        if not calculations:
            return jsonify({"status": "error", "message": "No final calculations found for this contract"}), 404
        
        # Retourner les données du résumé
        return jsonify({
            "status": "success",
            "assignment_id": assignment_id,
            "staff_name": assignment.staff.nickname if assignment.staff else assignment.archived_staff_name,
            "contract_type": assignment.contract_type,
            "start_date": assignment.start_date.isoformat(),
            "end_date": assignment.end_date.isoformat() if assignment.end_date else None,
            "total_days_worked": calculations.total_days_worked,
            "total_drinks_sold": calculations.total_drinks_sold,
            "total_special_commissions": calculations.total_special_commissions,
            "total_commission_paid": calculations.total_commission_paid,
            "total_salary_paid": calculations.total_salary_paid,
            "total_profit": calculations.total_profit,
            "average_daily_profit": calculations.average_daily_profit if calculations.total_days_worked > 0 else 0,
            "contract_status": assignment.status
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Erreur lors de la récupération du résumé pour assignment {assignment_id}: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

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
    if current_user.role == 'webdev':
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

    # Base query scoped to the user's agency with eager loading to prevent N+1 queries
    q = Assignment.query.filter_by(agency_id=agency_id).options(
        joinedload(Assignment.staff),
        joinedload(Assignment.venue),
        joinedload(Assignment.contract_calculations),
        joinedload(Assignment.performance_records)
    )

    # Apply filters (same logic as payroll_page)
    if selected_venue_id:
        q = q.filter(Assignment.venue_id == selected_venue_id)
    if selected_contract_type and selected_contract_type != 'all':
        q = q.filter(Assignment.contract_type == selected_contract_type)
    if selected_status:
        q = q.filter(Assignment.status == selected_status)
    else:
        q = q.filter(Assignment.status.in_(['active', 'ended', 'archived']))
    if search_nickname:
        q = q.join(StaffProfile).filter(StaffProfile.nickname.ilike(f'%{search_nickname}%'))
    if selected_manager_id:
        q = q.filter(Assignment.managed_by_user_id == selected_manager_id)

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            q = q.filter(Assignment.end_date >= start_date)
        except ValueError:
            pass # Ignore invalid date format for PDF generation
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            q = q.filter(Assignment.start_date <= end_date)
        except ValueError:
            pass # Ignore invalid date format for PDF generation
    
    status_order = db.case((Assignment.status == 'active', 1), (Assignment.status == 'ended', 2), (Assignment.status == 'archived', 3), else_=4).label("status_order")
    all_assignments = q.order_by(status_order, Assignment.start_date.asc()).all()
    
    # Récupérer tous les contrats de l'agence en une seule requête
    agency_contracts = AgencyContract.query.filter_by(agency_id=agency_id).all()
    contracts_dict = {contract.name: contract for contract in agency_contracts}
    
    # Process rows for display and calculation using ContractCalculations as single source of truth
    rows = []
    total_profit = 0
    total_days_worked = 0
    for a in all_assignments:
        # Obtenir la durée du contrat depuis le dictionnaire (pas de requête DB)
        contract = contracts_dict.get(a.contract_type)
        original_duration = contract.days if contract else 1
        
        # Use ContractCalculations as single source of truth
        try:
            from app.services.payroll_service import update_or_create_contract_calculations, process_assignments_batch
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
        # Récupérer le nom du contrat depuis le dictionnaire des contrats
        contract_name = None
        contract = contracts_dict.get(a.contract_type)
        if contract:
            contract_name = f"{contract.name} ({contract.days} days)"
            
        rows.append({
            "assignment": a,
            "days_worked": days_worked,
            "original_duration": original_duration,
            "contract_stats": contract_stats,
            "contract_name": contract_name
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
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    # Security: Ensure the assignment belongs to the user's agency
    assignment = Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).options(
        joinedload(Assignment.staff),
        joinedload(Assignment.manager),
        joinedload(Assignment.venue),
        joinedload(Assignment.performance_records)
    ).first_or_404()

    # Get contract duration from AgencyContract table
    contract = AgencyContract.query.filter_by(name=assignment.contract_type, agency_id=agency_id).first()
    original_duration = contract.days if contract else 1
    
    # Use ContractCalculations as single source of truth
    contract_calc = ContractCalculations.query.filter_by(assignment_id=assignment_id).first()

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
        # Fallback de sécurité si aucun calcul n'a été pré-calculé
        current_app.logger.warning(f"No pre-calculated ContractCalculations found for assignment {assignment_id}. Displaying zeros in PDF.")
        contract_stats = {"drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0}
        days_worked = len(assignment.performance_records) # On se base sur les records s'ils existent
    
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


@payroll_bp.route('/report/view/<int:assignment_id>')
@login_required
@manager_required
def report_view(assignment_id):
    """
    Affiche une vue HTML du rapport de contrat avec les mêmes données que le PDF.
    """
    from flask import session
    
    # Get current agency ID
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    # Security: Ensure the assignment belongs to the user's agency
    assignment = Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).options(
        joinedload(Assignment.staff),
        joinedload(Assignment.venue),
        joinedload(Assignment.contract_calculations),
        joinedload(Assignment.performance_records)
    ).first_or_404()

    # Get contract duration from AgencyContract table
    contract = AgencyContract.query.filter_by(name=assignment.contract_type, agency_id=agency_id).first()
    original_duration = contract.days if contract else 1
    
    # Use ContractCalculations as single source of truth
    try:
        from app.services.payroll_service import update_or_create_contract_calculations, process_assignments_batch
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
        current_app.logger.error(f"Error getting contract calculations for report view: {str(e)}")
        # Fallback to empty stats if service fails
        contract_stats = {"drinks": 0, "special_comm": 0, "salary": 0, "commission": 0, "profit": 0}
        days_worked = len(assignment.performance_records)
    
    return render_template('report_view.html',
                          assignment=assignment,
                          contract_stats=contract_stats,
                          days_worked=days_worked,
                          original_duration=original_duration,
                          report_date=date.today())


# --- API ENDPOINTS ---
@payroll_bp.route('/api/assignment/<int:assignment_id>/summary')
@login_required
@manager_required
def assignment_summary_api(assignment_id):
    """
    API endpoint pour récupérer le résumé des calculs d'un contrat.
    Utilise le service de paie pour calculer les totaux en temps réel.
    """
    from flask import session
    
    # Get current agency ID
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    # Security: Ensure the assignment belongs to the user's agency
    assignment = Assignment.query.filter_by(id=assignment_id, agency_id=agency_id).options(
        joinedload(Assignment.staff),
        joinedload(Assignment.venue),
        joinedload(Assignment.contract_calculations)
    ).first()
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404
    
    try:
        # Utiliser le service de paie pour calculer les totaux
        from app.services.payroll_service import update_or_create_contract_calculations, process_assignments_batch
        
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


# --- PERFORMANCE DASHBOARD ---
@payroll_bp.route('/dashboard')
@login_required
@super_admin_required
def payroll_dashboard():
    """
    Dashboard de performance pour analyser les données de paie avec des graphiques et statistiques.
    """
    from flask import session
    
    # Get current agency ID
    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        abort(403, "User not associated with an agency.")
    
    # Get filter arguments from request (same as payroll_page)
    selected_venue_id = request.args.get('venue_id', type=int)
    selected_contract_type = request.args.get('contract_type')
    selected_status = request.args.get('status')
    search_nickname = request.args.get('nickname')
    selected_manager_id = request.args.get('manager_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # Base query scoped to the user's agency with eager loading to prevent N+1 queries
    q = Assignment.query.filter_by(agency_id=agency_id).options(
        joinedload(Assignment.staff),
        joinedload(Assignment.venue),
        joinedload(Assignment.contract_calculations),
        joinedload(Assignment.performance_records)
    )
    
    # Apply filters (same logic as payroll_page)
    if selected_venue_id:
        q = q.filter(Assignment.venue_id == selected_venue_id)
    if selected_contract_type and selected_contract_type != 'all':
        q = q.filter(Assignment.contract_type == selected_contract_type)
    
    # Apply status filter
    if selected_status and selected_status != 'all':
        q = q.filter(Assignment.status == selected_status)
    
    if search_nickname:
        q = q.join(StaffProfile).filter(StaffProfile.nickname.ilike(f'%{search_nickname}%'))
    if selected_manager_id:
        q = q.filter(Assignment.managed_by_user_id == selected_manager_id)
    
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            q = q.filter(Assignment.end_date >= start_date)
        except ValueError:
            pass  # Ignore invalid date format for dashboard
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            q = q.filter(Assignment.start_date <= end_date)
        except ValueError:
            pass  # Ignore invalid date format for dashboard
    
    # Récupérer les assignments filtrés
    filtered_assignments = q.order_by(Assignment.start_date.desc()).all()
    
    # Générer les statistiques de performance
    from app.services.payroll_service import generate_performance_stats
    performance_stats = generate_performance_stats(filtered_assignments)
    
    # Fetch dynamic filter data, scoped to the agency
    agency_managers = User.query.filter_by(agency_id=agency_id).order_by(User.username).all()
    agency_venues = Venue.query.filter_by(agency_id=agency_id).order_by(Venue.name).all()
    
    # Debug: Log the filter data being passed
    current_app.logger.info(f"[DEBUG] Dashboard - Agency ID: {agency_id}")
    current_app.logger.info(f"[DEBUG] Dashboard - Managers found: {len(agency_managers)}")
    current_app.logger.info(f"[DEBUG] Dashboard - Venues found: {len(agency_venues)}")
    if selected_manager_id:
        current_app.logger.info(f"[DEBUG] Dashboard - Selected manager ID: {selected_manager_id} (type: {type(selected_manager_id)})")
        for manager in agency_managers:
            current_app.logger.info(f"[DEBUG] Dashboard - Manager {manager.id} (type: {type(manager.id)}): {manager.username}")
    
    # Get the selected manager object if manager_id is provided
    selected_manager = None
    if selected_manager_id:
        selected_manager = User.query.get(selected_manager_id)
    
    # Get the selected venue object if venue_id is provided
    selected_venue = None
    if selected_venue_id:
        selected_venue = Venue.query.get(selected_venue_id)
    
    # Prepare filter data for template (same approach as PDF route)
    agency_contracts_for_filter = AgencyContract.query.filter_by(agency_id=agency_id).order_by(AgencyContract.name).all()
    filter_data = {
        "venues": agency_venues,
        "managers": agency_managers,
        "contract_types": agency_contracts_for_filter
    }
    
    # Pass data to the template with names expected by the frontend
    return render_template('payroll/dashboard.html',
                           active_filters=request.args,
                           stats=performance_stats,
                           contracts=filtered_assignments,
                           filter_data=filter_data,
                           selected_manager=selected_manager,
                           selected_venue=selected_venue)


@payroll_bp.route('/dashboard/pdf')
@login_required
@payroll_view_required
def payroll_dashboard_pdf():
    from app.services.payroll_service import generate_performance_stats
    from app.models import User

    if current_user.role == 'webdev':
        agency_id = session.get('current_agency_id', current_user.agency_id)
    else:
        agency_id = current_user.agency_id
    
    if not agency_id:
        abort(403)

    q = Assignment.query.filter_by(agency_id=agency_id).options(
        joinedload(Assignment.staff),
        joinedload(Assignment.venue),
        joinedload(Assignment.contract_calculations),
        joinedload(Assignment.performance_records)
    )

    # Apply all filters from the request args (same logic as main dashboard)
    selected_venue_id = request.args.get('venue_id', type=int)
    selected_contract_type = request.args.get('contract_type')
    selected_status = request.args.get('status')
    search_nickname = request.args.get('nickname')
    selected_manager_id = request.args.get('manager_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if selected_venue_id:
        q = q.filter(Assignment.venue_id == selected_venue_id)
    if selected_contract_type and selected_contract_type != 'all':
        q = q.filter(Assignment.contract_type == selected_contract_type)
    if selected_status and selected_status != 'all':
        q = q.filter(Assignment.status == selected_status)
    if search_nickname:
        q = q.join(StaffProfile).filter(StaffProfile.nickname.ilike(f'%{search_nickname}%'))
    if selected_manager_id:
        q = q.filter(Assignment.managed_by_user_id == selected_manager_id)
    
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            q = q.filter(Assignment.end_date >= start_date)
        except ValueError:
            pass  # Ignore invalid date format for PDF
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            q = q.filter(Assignment.start_date <= end_date)
        except ValueError:
            pass  # Ignore invalid date format for PDF

    filtered_assignments = q.order_by(Assignment.start_date.desc()).all()
    performance_stats = generate_performance_stats(filtered_assignments)

    # Prepare header data for PDF
    header_data = {
        'manager_name': User.query.get(selected_manager_id).username if selected_manager_id else 'All Managers',
        'status': selected_status.capitalize() if selected_status else 'All Statuses',
        'date_range': f"{start_date_str} to {end_date_str}" if start_date_str and end_date_str else 'All Time',
        'venue': Venue.query.get(selected_venue_id).name if selected_venue_id else 'All Venues',
        'contract_type': selected_contract_type.capitalize() if selected_contract_type else 'All Types'
    }

    rendered_html = render_template(
        'payroll/dashboard_pdf.html',
        stats=performance_stats,
        contracts=filtered_assignments,
        header_data=header_data,
        today_date=date.today().strftime('%Y-%m-%d')
    )
    
    pdf = HTML(string=rendered_html, base_url=request.url_root).write_pdf()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=performance_dashboard_{date.today().isoformat()}.pdf'
    
    return response