# app/services/payroll_service.py

import time as time_module
from app import db
from app.models import Assignment, PerformanceRecord, ContractCalculations, AgencyContract, StaffProfile
from datetime import datetime, time
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from flask import current_app


def calculate_lateness_penalty(record, agency_contract):
    """
    Calcule la pénalité de retard basée sur les paramètres du contrat d'agence.
    
    Args:
        record: PerformanceRecord avec arrival_time
        agency_contract: AgencyContract avec les paramètres de pénalité
        
    Returns:
        float: Montant de la pénalité de retard
    """
    if not record.arrival_time or not agency_contract.late_cutoff_time:
        return 0.0
    
    # Convertir l'heure limite en objet time
    try:
        cutoff_hour, cutoff_minute = map(int, agency_contract.late_cutoff_time.split(':'))
        cutoff_time = time(cutoff_hour, cutoff_minute)
    except (ValueError, AttributeError):
        return 0.0
    
    # Si l'arrivée est avant l'heure limite, pas de pénalité
    if record.arrival_time <= cutoff_time:
        return 0.0
    
    # Calculer les minutes de retard
    arrival_minutes = record.arrival_time.hour * 60 + record.arrival_time.minute
    cutoff_minutes = cutoff_time.hour * 60 + cutoff_time.minute
    late_minutes = arrival_minutes - cutoff_minutes
    
    if late_minutes <= 0:
        return 0.0
    
    # Calculer la pénalité
    # Première minute: pénalité fixe (first_minute_penalty)
    # Minutes suivantes: pénalité par minute (additional_minute_penalty)
    first_minute_penalty = agency_contract.first_minute_penalty if agency_contract.first_minute_penalty is not None else 0.0
    additional_minute_penalty = agency_contract.additional_minute_penalty if agency_contract.additional_minute_penalty is not None else 0.0
    
    penalty = first_minute_penalty
    
    if late_minutes > 1:
        additional_minutes = late_minutes - 1
        penalty += additional_minutes * additional_minute_penalty
    
    return penalty


def process_assignments_batch(assignments):
    """
    Traite une liste d'assignments en lot pour optimiser les performances.
    Effectue seulement 2 requêtes DB au lieu de N*4 requêtes.
    
    Args:
        assignments (list): Liste d'objets Assignment avec performance_records préchargés
        
    Returns:
        dict: Dictionnaire {assignment_id: ContractCalculations} des calculs mis à jour
    """
    if not assignments:
        return {}
    
    batch_start = time_module.time()
    assignment_ids = [a.id for a in assignments]
    agency_ids = list(set(a.agency_id for a in assignments))
    
    # PRÉ-REQUÊTE 1: Récupérer tous les AgencyContract nécessaires
    agency_contracts_query = AgencyContract.query.filter(
        AgencyContract.agency_id.in_(agency_ids)
    ).all()
    
    # Créer un dictionnaire pour accès rapide: (contract_type, agency_id) -> AgencyContract
    contracts_dict = {}
    for contract in agency_contracts_query:
        key = (contract.name, contract.agency_id)
        contracts_dict[key] = contract
    
    # PRÉ-REQUÊTE 2: Récupérer tous les ContractCalculations existants
    existing_calculations = ContractCalculations.query.filter(
        ContractCalculations.assignment_id.in_(assignment_ids)
    ).all()
    
    # Créer un dictionnaire pour accès rapide: assignment_id -> ContractCalculations
    calculations_dict = {calc.assignment_id: calc for calc in existing_calculations}
    
    current_app.logger.info(f"[PERF] Batch pre-queries finished in {(time_module.time() - batch_start):.3f}s")
    
    # TRAITEMENT EN MÉMOIRE: Itérer sur les assignments sans nouvelles requêtes DB
    results = {}
    calc_start = time_module.time()
    
    for assignment in assignments:
        # Récupérer le contrat depuis le dictionnaire (pas de requête DB)
        contract_key = (assignment.contract_type, assignment.agency_id)
        agency_contract = contracts_dict.get(contract_key)
        
        # Utiliser les performance_records déjà chargés (subqueryload)
        performance_records = assignment.performance_records
        
        # Initialiser les totaux
        total_salary = 0.0
        total_commission = 0.0
        total_profit = 0.0
        days_worked = len(performance_records)
        total_drinks = 0
        total_special_comm = 0.0
        
        # Calculer le salaire de base par jour
        if agency_contract and agency_contract.days > 0:
            base_daily_salary = assignment.base_salary / agency_contract.days
        else:
            base_daily_salary = assignment.base_salary
        
        # Calculer les totaux à partir des performances
        for record in performance_records:
            total_drinks += record.drinks_sold if record.drinks_sold is not None else 0
            total_special_comm += record.special_commissions if record.special_commissions is not None else 0.0
            
            # Utiliser les valeurs journalières comme source de vérité
            total_salary += record.daily_salary if record.daily_salary is not None else 0.0
            total_profit += record.daily_profit if record.daily_profit is not None else 0.0

            # Le calcul de la commission reste basé sur les règles du contrat
            if agency_contract and record.drinks_sold and record.drinks_sold > 0:
                drink_commission = record.drinks_sold * agency_contract.staff_commission
                total_commission += drink_commission

        # Le profit total est maintenant la somme des profits journaliers, donc plus besoin de le calculer ici.
        # Le salaire total est la somme des salaires journaliers.
        
        # Récupérer ou créer ContractCalculations depuis le dictionnaire
        contract_calc = calculations_dict.get(assignment.id)
        
        if contract_calc:
            # Mettre à jour les valeurs existantes
            contract_calc.total_salary = total_salary
            contract_calc.total_commission = total_commission
            contract_calc.total_profit = total_profit
            contract_calc.days_worked = days_worked
            contract_calc.total_drinks = total_drinks
            contract_calc.total_special_comm = total_special_comm
            contract_calc.last_updated = datetime.utcnow()
        else:
            # Créer un nouveau calcul
            contract_calc = ContractCalculations(
                assignment_id=assignment.id,
                total_salary=total_salary,
                total_commission=total_commission,
                total_profit=total_profit,
                days_worked=days_worked,
                total_drinks=total_drinks,
                total_special_comm=total_special_comm,
                last_updated=datetime.utcnow()
            )
            db.session.add(contract_calc)
            calculations_dict[assignment.id] = contract_calc
        
        results[assignment.id] = contract_calc
    
    # UN SEUL COMMIT pour tous les calculs
    try:
        db.session.commit()
        calc_time = time_module.time() - calc_start
        current_app.logger.info(f"[PERF] Batch of {len(assignments)} assignments processed in {calc_time:.3f}s")
        return results
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Erreur lors de la sauvegarde batch: {str(e)}")


def calculate_totals_with_aggregation(assignment_ids):
    """
    Calcule les totaux pour une liste d'assignment_ids en utilisant une seule
    requête d'agrégation SQL pour une performance maximale.
    """
    if not assignment_ids:
        return {}

    batch_start = time_module.time()

    # ÉTAPE 1: Requête d'agrégation pour calculer tous les totaux en une seule fois.
    totals_by_assignment = db.session.query(
        PerformanceRecord.assignment_id,
        func.sum(PerformanceRecord.daily_salary).label('total_salary'),
        func.sum(PerformanceRecord.daily_profit).label('total_profit'),
        func.sum(PerformanceRecord.drinks_sold).label('total_drinks'),
        func.sum(PerformanceRecord.special_commissions).label('total_special_comm'),
        func.count(PerformanceRecord.id).label('days_worked')
    ).filter(
        PerformanceRecord.assignment_id.in_(assignment_ids)
    ).group_by(
        PerformanceRecord.assignment_id
    ).all()

    # Transformer les résultats en un dictionnaire pour un accès facile.
    totals_dict = {
        res.assignment_id: {
            'total_salary': res.total_salary or 0.0,
            'total_profit': res.total_profit or 0.0,
            'total_drinks': res.total_drinks or 0,
            'total_special_comm': res.total_special_comm or 0.0,
            'days_worked': res.days_worked or 0
        }
        for res in totals_by_assignment
    }

    # ÉTAPE 2: Mise à jour de la table ContractCalculations en batch.
    existing_calcs = ContractCalculations.query.filter(
        ContractCalculations.assignment_id.in_(assignment_ids)
    ).all()
    calcs_dict = {calc.assignment_id: calc for calc in existing_calcs}
    
    assignments_to_process = Assignment.query.options(joinedload(Assignment.staff)).filter(Assignment.id.in_(assignment_ids)).all()
    assignments_dict = {a.id: a for a in assignments_to_process}

    for assignment_id in assignment_ids:
        totals = totals_dict.get(assignment_id, {})
        
        # Le calcul de la commission doit encore se faire en Python car il dépend des règles du contrat
        total_commission = 0.0
        # assignment = assignments_dict.get(assignment_id)
        # if assignment:
        #     # Note: This part still requires the contract rules. For this optimization, 
        #     # we'll simplify and assume a fixed commission rate if contract isn't pre-loaded.
        #     # A full optimization would involve pre-loading contracts as well.
        #     # This logic should be adapted if commission rules are complex.
        #     contract = assignment.get_contract() # Assuming a helper method exists
        #     if contract and totals.get('total_drinks', 0) > 0:
        #         total_commission = totals.get('total_drinks', 0) * contract.staff_commission


        if assignment_id in calcs_dict:
            # Mise à jour
            calc = calcs_dict[assignment_id]
            calc.total_salary = totals.get('total_salary', 0.0)
            calc.total_profit = totals.get('total_profit', 0.0)
            calc.total_drinks = totals.get('total_drinks', 0)
            calc.total_special_comm = totals.get('total_special_comm', 0.0)
            calc.days_worked = totals.get('days_worked', 0)
            calc.total_commission = total_commission
            calc.last_updated = datetime.utcnow()
        else:
            # Création
            new_calc = ContractCalculations(
                assignment_id=assignment_id,
                total_salary=totals.get('total_salary', 0.0),
                total_profit=totals.get('total_profit', 0.0),
                total_drinks=totals.get('total_drinks', 0),
                total_special_comm=totals.get('total_special_comm', 0.0),
                days_worked=totals.get('days_worked', 0),
                total_commission=total_commission,
                last_updated=datetime.utcnow()
            )
            db.session.add(new_calc)

    try:
        db.session.commit()
        calc_time = time_module.time() - batch_start
        current_app.logger.info(f"[PERF] Batch AGGREGATE de {len(assignment_ids)} assignments traité en {calc_time:.3f}s")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during aggregate batch save: {str(e)}")
        raise

    return ContractCalculations.query.filter(ContractCalculations.assignment_id.in_(assignment_ids)).all()


def update_or_create_contract_calculations(assignment_id):
    """
    ⚠️ FONCTION OBSOLÈTE - UTILISER process_assignments_batch() POUR DE MEILLEURES PERFORMANCES ⚠️
    
    Cette fonction est conservée uniquement comme fallback de sécurité.
    Elle génère des requêtes N+1 et doit être évitée dans les boucles.
    
    Args:
        assignment_id (int): ID de l'assignment pour lequel calculer les totaux
        
    Returns:
        ContractCalculations: L'objet ContractCalculations créé ou mis à jour
    """
    import warnings
    warnings.warn(
        "update_or_create_contract_calculations est obsolète. "
        "Utiliser process_assignments_batch() pour de meilleures performances.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Début du chronométrage pour ce calcul
    calc_start = time_module.time()
    
    # Récupérer l'assignment et vérifier qu'il existe
    assignment = Assignment.query.get(assignment_id)
    if not assignment:
        raise ValueError(f"Assignment avec l'ID {assignment_id} n'existe pas")
    
    # Récupérer toutes les performances pour cet assignment
    performance_records = PerformanceRecord.query.filter_by(assignment_id=assignment_id).all()
    
    # Récupérer le contrat de l'agence pour les règles de calcul
    agency_contract = AgencyContract.query.filter_by(
        name=assignment.contract_type,
        agency_id=assignment.agency_id
    ).first()
    
    # Initialiser les totaux
    total_salary = 0.0
    total_commission = 0.0
    total_profit = 0.0
    days_worked = len(performance_records)
    total_drinks = 0
    total_special_comm = 0.0
    
    # Calculer le salaire de base par jour
    if agency_contract and agency_contract.days > 0:
        base_daily_salary = assignment.base_salary / agency_contract.days
    else:
        base_daily_salary = assignment.base_salary  # Fallback si pas de durée définie
    
    # Calculer les totaux à partir des performances
    for record in performance_records:
        # Total des boissons vendues
        total_drinks += record.drinks_sold
        
        # Total des commissions spéciales
        total_special_comm += record.special_commissions
        
        # Calcul des commissions sur les boissons
        if agency_contract and record.drinks_sold > 0:
            drink_commission = record.drinks_sold * agency_contract.staff_commission
            total_commission += drink_commission
        
        # Calculer la pénalité de retard en temps réel
        lateness_penalty = calculate_lateness_penalty(record, agency_contract) if agency_contract else 0.0
        
        # Ajouter le salaire de base quotidien, les bonus et soustraire les malus
        total_salary += base_daily_salary
        total_salary += record.bonus
        total_salary -= record.malus
        total_salary -= lateness_penalty
    
    # Calculer le profit total (revenus - coûts)
    # Le profit est: (revenus des boissons + commissions spéciales) - (salaire + commissions staff)
    total_revenue = 0.0
    if agency_contract and total_drinks > 0:
        total_revenue += total_drinks * agency_contract.drink_price
    total_revenue += total_special_comm  # Ajouter les commissions spéciales aux revenus
    
    total_costs = total_salary + total_commission
    total_profit = total_revenue - total_costs
    
    # Chercher si un calcul existe déjà pour cet assignment
    contract_calc = ContractCalculations.query.filter_by(assignment_id=assignment_id).first()
    
    if contract_calc:
        # Mettre à jour les valeurs existantes
        contract_calc.total_salary = total_salary
        contract_calc.total_commission = total_commission
        contract_calc.total_profit = total_profit
        contract_calc.days_worked = days_worked
        contract_calc.total_drinks = total_drinks
        contract_calc.total_special_comm = total_special_comm
        contract_calc.last_updated = datetime.utcnow()
    else:
        # Créer un nouveau calcul
        contract_calc = ContractCalculations(
            assignment_id=assignment_id,
            total_salary=total_salary,
            total_commission=total_commission,
            total_profit=total_profit,
            days_worked=days_worked,
            total_drinks=total_drinks,
            total_special_comm=total_special_comm,
            last_updated=datetime.utcnow()
        )
        db.session.add(contract_calc)
    
    # Sauvegarder les changements
    try:
        db.session.commit()
        
        # Log de performance pour ce calcul
        calc_time = time_module.time() - calc_start
        current_app.logger.info(f"[PERF] Calcul contract {assignment_id} terminé en {calc_time:.3f}s")
        
        return contract_calc
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Erreur lors de la sauvegarde des calculs: {str(e)}")


def get_contract_summary(assignment_id):
    """
    Récupère le résumé des calculs d'un contrat.
    
    Args:
        assignment_id (int): ID de l'assignment
        
    Returns:
        dict: Résumé des calculs ou None si pas trouvé
    """
    contract_calc = ContractCalculations.query.filter_by(assignment_id=assignment_id).first()
    
    if not contract_calc:
        return None
    
    return {
        'total_salary': contract_calc.total_salary,
        'total_commission': contract_calc.total_commission,
        'total_profit': contract_calc.total_profit,
        'days_worked': contract_calc.days_worked,
        'total_drinks': contract_calc.total_drinks,
        'total_special_comm': contract_calc.total_special_comm,
        'last_updated': contract_calc.last_updated.isoformat() if contract_calc.last_updated else None
    }


def get_staff_performance_summary(staff_id, start_date=None, end_date=None):
    """
    Agrège les données de ContractCalculations et PerformanceRecord pour un staff donné
    et retourne un dictionnaire contenant les totaux et l'historique détaillé.
    
    Args:
        staff_id (int): ID du staff profile
        start_date (date, optional): Date de début pour filtrer les données
        end_date (date, optional): Date de fin pour filtrer les données
        
    Returns:
        dict: Dictionnaire contenant les totaux et l'historique détaillé
    """
    # Vérifier que le staff existe
    staff = StaffProfile.query.get(staff_id)
    if not staff:
        raise ValueError(f"Staff avec l'ID {staff_id} n'existe pas")
    
    # Récupérer tous les assignments du staff
    assignments_query = Assignment.query.filter_by(staff_id=staff_id)
    
    # Appliquer les filtres de date si fournis
    if start_date:
        assignments_query = assignments_query.filter(Assignment.end_date >= start_date)
    if end_date:
        assignments_query = assignments_query.filter(Assignment.start_date <= end_date)
    
    assignments = assignments_query.all()
    
    # Initialiser les totaux globaux
    total_days_worked = 0
    total_drinks_sold = 0
    total_special_comm = 0.0
    total_salary_paid = 0.0
    total_commission_paid = 0.0
    total_bar_profit = 0.0
    
    # Liste pour stocker l'historique détaillé
    detailed_history = []
    
    # Traiter chaque assignment
    for assignment in assignments:
        # Récupérer le contrat d'agence pour les règles de calcul
        agency_contract = AgencyContract.query.filter_by(
            name=assignment.contract_type,
            agency_id=assignment.agency_id
        ).first()
        
        # Calculer le salaire de base par jour
        if agency_contract and agency_contract.days > 0:
            base_daily_salary = assignment.base_salary / agency_contract.days
        else:
            # Fallback avec les types de contrat standards
            contract_days = {"1day": 1, "10days": 10, "1month": 30}.get(assignment.contract_type, 1)
            base_daily_salary = assignment.base_salary / contract_days if contract_days > 0 else assignment.base_salary
        
        # Récupérer les enregistrements de performance pour cet assignment
        performance_query = PerformanceRecord.query.filter_by(assignment_id=assignment.id)
        
        # Appliquer les filtres de date aux enregistrements
        if start_date:
            performance_query = performance_query.filter(PerformanceRecord.record_date >= start_date)
        if end_date:
            performance_query = performance_query.filter(PerformanceRecord.record_date <= end_date)
        
        performance_records = performance_query.order_by(PerformanceRecord.record_date).all()
        
        # Traiter chaque enregistrement de performance
        for record in performance_records:
            # Calculer la pénalité de retard
            lateness_penalty = calculate_lateness_penalty(record, agency_contract) if agency_contract else 0.0
            
            # Calculer le salaire quotidien
            daily_salary = base_daily_salary + (record.bonus or 0) - (record.malus or 0) - lateness_penalty
            
            # Calculer la commission quotidienne
            if agency_contract:
                daily_commission = (record.drinks_sold or 0) * agency_contract.staff_commission
                bar_revenue = ((record.drinks_sold or 0) * agency_contract.drink_price) + (record.special_commissions or 0)
            else:
                # Fallback avec les valeurs par défaut
                daily_commission = (record.drinks_sold or 0) * 100  # 100 THB par boisson
                bar_revenue = ((record.drinks_sold or 0) * 120) + (record.special_commissions or 0)  # 120 THB par boisson
            
            # Calculer le profit quotidien
            daily_profit = bar_revenue - daily_salary
            
            # Ajouter aux totaux
            total_salary_paid += daily_salary
            total_commission_paid += daily_commission
            total_drinks_sold += record.drinks_sold or 0
            total_special_comm += record.special_commissions or 0
            total_days_worked += 1
            
            # Ajouter le profit quotidien depuis le champ daily_profit du record
            total_bar_profit += record.daily_profit or 0
            
            # Ajouter à l'historique détaillé
            detailed_history.append({
                'assignment_id': assignment.id,
                'venue_name': assignment.venue.name if assignment.venue else 'N/A',
                'contract_role': assignment.contract_role,
                'contract_type': assignment.contract_type,
                'record_date': record.record_date.isoformat(),
                'drinks_sold': record.drinks_sold or 0,
                'special_commissions': record.special_commissions or 0,
                'bonus': record.bonus or 0,
                'malus': record.malus or 0,
                'lateness_penalty': lateness_penalty,
                'daily_salary': daily_salary,
                'daily_commission': daily_commission,
                'daily_profit': record.daily_profit or 0,
                'arrival_time': record.arrival_time.strftime('%H:%M') if record.arrival_time else None,
                'departure_time': record.departure_time.strftime('%H:%M') if record.departure_time else None
            })
    
    # Récupérer les calculs de contrat agrégés (si disponibles)
    contract_calculations = []
    for assignment in assignments:
        calc = ContractCalculations.query.filter_by(assignment_id=assignment.id).first()
        if calc:
            contract_calculations.append({
                'assignment_id': assignment.id,
                'venue_name': assignment.venue.name if assignment.venue else 'N/A',
                'contract_role': assignment.contract_role,
                'contract_type': assignment.contract_type,
                'start_date': assignment.start_date.isoformat(),
                'end_date': assignment.end_date.isoformat(),
                'total_salary': calc.total_salary,
                'total_commission': calc.total_commission,
                'total_profit': calc.total_profit,
                'days_worked': calc.days_worked,
                'total_drinks': calc.total_drinks,
                'total_special_comm': calc.total_special_comm,
                'last_updated': calc.last_updated.isoformat() if calc.last_updated else None
            })
    
    # Retourner le résumé complet
    return {
        'staff_info': {
            'id': staff.id,
            'nickname': staff.nickname,
            'first_name': staff.first_name,
            'last_name': staff.last_name,
            'status': staff.status
        },
        'summary_totals': {
            'total_days_worked': total_days_worked,
            'total_drinks_sold': total_drinks_sold,
            'total_special_comm': total_special_comm,
            'total_salary_paid': total_salary_paid,
            'total_commission_paid': total_commission_paid,
            'total_bar_profit': total_bar_profit
        },
        'detailed_history': detailed_history,
        'contract_calculations': contract_calculations,
        'filter_period': {
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None
        }
    }


def recalculate_all_contracts():
    """
    Recalcule tous les contrats existants.
    Utile pour les migrations ou corrections de données.
    
    Returns:
        int: Nombre de contrats recalculés
    """
    assignments = Assignment.query.all()
    count = 0
    
    for assignment in assignments:
        try:
            update_or_create_contract_calculations(assignment.id)
            count += 1
        except Exception as e:
            print(f"Erreur lors du recalcul du contrat {assignment.id}: {str(e)}")
            continue
    
    return count


def generate_performance_stats(assignments):
    """
    Generates performance statistics based on filtered contracts.
    Analyzes actual work history (PerformanceRecord) for each contract.
    
    Args:
        assignments (list): List of Assignment objects with preloaded performance_records
        
    Returns:
        dict: Dictionary containing performance statistics
    """
    if not assignments:
        return {
            'total_profit': 0,
            'total_days_worked': 0,
            'unique_staff_count': 0,
            'contract_breakdown': {
                'by_type': {},
                'by_status': {'complete': 0, 'incomplete': 0}
            }
        }
    
    # Initialize counters
    total_profit = 0
    total_days_worked = 0
    unique_staff_ids = set()
    
    # Dictionaries for breakdown
    contract_type_counts = {}
    contract_status_counts = {'complete': 0, 'incomplete': 0}
    
    # Process each assignment
    for assignment in assignments:
        # Count unique staff
        if assignment.staff:
            unique_staff_ids.add(assignment.staff.id)
        elif assignment.archived_staff_name:
            # For deleted staff, use unique identifier based on name
            unique_staff_ids.add(f"archived_{assignment.archived_staff_name}")
        
        # Get contract calculations (single source of truth)
        contract_calc = ContractCalculations.query.filter_by(assignment_id=assignment.id).first()
        
        if contract_calc:
            # Use pre-calculated data
            total_profit += contract_calc.total_profit or 0
            total_days_worked += contract_calc.days_worked or 0
            
            # Count by contract type
            contract_type = assignment.contract_type
            if contract_type not in contract_type_counts:
                contract_type_counts[contract_type] = {
                    'count': 0,
                    'total_profit': 0,
                    'total_days': 0
                }
            contract_type_counts[contract_type]['count'] += 1
            contract_type_counts[contract_type]['total_profit'] += contract_calc.total_profit or 0
            contract_type_counts[contract_type]['total_days'] += contract_calc.days_worked or 0
            
            # Determine if contract is complete or incomplete
            # Get expected duration from AgencyContract
            agency_contract = AgencyContract.query.filter_by(
                name=assignment.contract_type,
                agency_id=assignment.agency_id
            ).first()
            
            expected_days = agency_contract.days if agency_contract else 1
            actual_days = contract_calc.days_worked or 0
            
            if actual_days >= expected_days:
                contract_status_counts['complete'] += 1
            else:
                contract_status_counts['incomplete'] += 1
                
        else:
            # Fallback: calculate manually if no ContractCalculations
            days_worked = len(assignment.performance_records)
            total_days_worked += days_worked
            
            # Calculate profit manually
            daily_profit = 0
            for record in assignment.performance_records:
                daily_profit += record.daily_profit or 0
            total_profit += daily_profit
            
            # Count by contract type
            contract_type = assignment.contract_type
            if contract_type not in contract_type_counts:
                contract_type_counts[contract_type] = {
                    'count': 0,
                    'total_profit': 0,
                    'total_days': 0
                }
            contract_type_counts[contract_type]['count'] += 1
            contract_type_counts[contract_type]['total_profit'] += daily_profit
            contract_type_counts[contract_type]['total_days'] += days_worked
            
            # Determine status
            agency_contract = AgencyContract.query.filter_by(
                name=assignment.contract_type,
                agency_id=assignment.agency_id
            ).first()
            
            expected_days = agency_contract.days if agency_contract else 1
            if days_worked >= expected_days:
                contract_status_counts['complete'] += 1
            else:
                contract_status_counts['incomplete'] += 1
    
    # Build contract type breakdown
    contract_breakdown = {
        'by_type': contract_type_counts,
        'by_status': contract_status_counts
    }
    
    return {
        'total_profit': total_profit,
        'total_days_worked': total_days_worked,
        'unique_staff_count': len(unique_staff_ids),
        'contract_breakdown': contract_breakdown
    }
