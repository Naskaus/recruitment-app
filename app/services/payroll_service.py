# app/services/payroll_service.py

from app import db
from app.models import Assignment, PerformanceRecord, ContractCalculations, AgencyContract
from datetime import datetime, time
from sqlalchemy import func


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


def update_or_create_contract_calculations(assignment_id):
    """
    Calcule et sauvegarde les totaux d'un contrat basés sur les performances enregistrées.
    
    Args:
        assignment_id (int): ID de l'assignment pour lequel calculer les totaux
        
    Returns:
        ContractCalculations: L'objet ContractCalculations créé ou mis à jour
    """
    
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
