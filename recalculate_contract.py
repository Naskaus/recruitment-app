# recalculate_contract.py

import os
from app import create_app, db
from app.models import Assignment, ContractCalculations
from app.services.payroll_service import process_assignments_batch
from sqlalchemy.orm import subqueryload

# Crée une instance de l'application Flask pour avoir le contexte
app = create_app()

def run_recalculation(assignment_id):
    """
    Force le recalcul pour un seul assignment et met à jour la base de données.
    """
    with app.app_context():
        print(f"--- Lancement du recalcul pour l'Assignment ID: {assignment_id} ---")

        # 1. Récupérer l'assignment cible avec ses performances pré-chargées
        assignment = Assignment.query.options(
            subqueryload(Assignment.performance_records)
        ).get(assignment_id)

        if not assignment:
            print(f"ERREUR: Assignment avec l'ID {assignment_id} non trouvé.")
            return

        print(f"Assignment trouvé pour le staff: {assignment.staff.nickname if assignment.staff else 'N/A'}")
        print(f"Nombre de performance records trouvés: {len(assignment.performance_records)}")

        # 2. Appeler la fonction de calcul corrigée
        print("Appel de process_assignments_batch...")
        results = process_assignments_batch([assignment]) # La fonction attend une liste

        if not results:
            print("ERREUR: Le processus de calcul n'a retourné aucun résultat.")
            return

        # 3. Vérifier et afficher les nouvelles valeurs calculées
        updated_calc = results.get(assignment_id)
        if updated_calc:
            print("\n--- NOUVEAUX TOTAUX CALCULÉS ---")
            print(f"  Jours travaillés: {updated_calc.days_worked}")
            print(f"  Boissons vendues: {updated_calc.total_drinks}")
            print(f"  Salaire total payé: {updated_calc.total_salary}")
            print(f"  Profit total: {updated_calc.total_profit}")
            print("---------------------------------")
            print("\nSUCCÈS : La base de données a été mise à jour.")
        else:
            print("ERREUR: Le résultat du calcul est vide pour cet assignment.")

if __name__ == "__main__":
    # Remplacez 7 par l'ID de l'assignment que vous voulez tester
    TARGET_ASSIGNMENT_ID = 7
    run_recalculation(TARGET_ASSIGNMENT_ID)
