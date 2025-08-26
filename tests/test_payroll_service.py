# tests/test_payroll_service.py

import unittest
from datetime import date, datetime, time
from app import create_app, db
from app.models import Agency, User, Role, StaffProfile, Venue, AgencyContract, Assignment, PerformanceRecord, ContractCalculations
from app.services.payroll_service import update_or_create_contract_calculations


class TestPayrollService(unittest.TestCase):
    
    def setUp(self):
        """Configuration initiale pour chaque test"""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
            self._create_test_data()
    
    def tearDown(self):
        """Nettoyage après chaque test"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
    
    def _create_test_data(self):
        """Créer les données de test nécessaires"""
        # Créer une agence
        self.agency = Agency(name="Test Agency Payroll")
        db.session.add(self.agency)
        
        # Créer un rôle
        self.role = Role(name="Test Manager Role")
        db.session.add(self.role)
        
        # Créer un utilisateur
        self.user = User(username="test_manager_payroll", role_id=1, agency_id=1)
        self.user.set_password("password")
        db.session.add(self.user)
        
        # Créer un profil staff
        self.staff = StaffProfile(
            agency_id=1,
            nickname="Test Staff Payroll",
            dob=date(1990, 1, 1),
            status="Active"
        )
        db.session.add(self.staff)
        
        # Créer un venue
        self.venue = Venue(name="Test Venue Payroll", agency_id=1)
        db.session.add(self.venue)
        
        # Créer un contrat d'agence
        self.agency_contract = AgencyContract(
            name="Test Contract Payroll",
            days=10,
            agency_id=1,
            late_cutoff_time="19:30",
            first_minute_penalty=0.0,
            additional_minute_penalty=5.0,
            drink_price=220.0,
            staff_commission=100.0
        )
        db.session.add(self.agency_contract)
        
        # Créer un assignment
        self.assignment = Assignment(
            agency_id=1,
            staff_id=1,
            managed_by_user_id=1,
            venue_id=1,
            contract_role="Dancer",
            contract_type="Test Contract Payroll",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
            base_salary=1000.0,
            status="ongoing"
        )
        db.session.add(self.assignment)
        
        db.session.commit()
    
    def test_calculation_nominal(self):
        """Test des calculs avec des valeurs connues"""
        with self.app.app_context():
            # Récupérer l'assignment depuis la base de données
            assignment = Assignment.query.first()
            
            # Créer deux PerformanceRecord avec des valeurs connues
            record1 = PerformanceRecord(
                assignment_id=assignment.id,
                record_date=date(2024, 1, 1),
                arrival_time=time(19, 0),  # À l'heure
                departure_time=time(2, 0),
                drinks_sold=5,
                special_commissions=50.0,
                bonus=20.0,
                malus=0.0,
                lateness_penalty=0.0
            )
            db.session.add(record1)
            
            record2 = PerformanceRecord(
                assignment_id=assignment.id,
                record_date=date(2024, 1, 2),
                arrival_time=time(19, 45),  # 15 minutes en retard
                departure_time=time(2, 0),
                drinks_sold=3,
                special_commissions=30.0,
                bonus=0.0,
                malus=10.0,
                lateness_penalty=70.0  # 15 min * 5 THB/min = 75 THB, mais première minute = 0
            )
            db.session.add(record2)
            
            db.session.commit()
            
            # Appeler la fonction de calcul
            contract_calc = update_or_create_contract_calculations(assignment.id)
            
            # Vérifier les calculs
            # Le service ajoute le salaire de base complet pour chaque jour travaillé
            # Jour 1: 1000 (base) + 20 (bonus) - 0 (malus) - 0 (retard) = 1020 THB
            # Jour 2: 1000 (base) + 0 (bonus) - 10 (malus) - 70 (retard) = 920 THB
            # Total salaire = 1020 + 920 = 1940 THB
            expected_total_salary = 1940.0
            self.assertEqual(contract_calc.total_salary, expected_total_salary)
            
            # Commission sur les boissons
            # Jour 1: 5 boissons * 100 THB = 500 THB
            # Jour 2: 3 boissons * 100 THB = 300 THB
            # Total commission = 500 + 300 = 800 THB
            expected_total_commission = 800.0
            self.assertEqual(contract_calc.total_commission, expected_total_commission)
            
            # Total boissons vendues
            # Jour 1: 5 boissons
            # Jour 2: 3 boissons
            # Total = 5 + 3 = 8 boissons
            expected_total_drinks = 8
            self.assertEqual(contract_calc.total_drinks, expected_total_drinks)
            
            # Total commissions spéciales
            # Jour 1: 50 THB
            # Jour 2: 30 THB
            # Total = 50 + 30 = 80 THB
            expected_total_special_comm = 80.0
            self.assertEqual(contract_calc.total_special_comm, expected_total_special_comm)
            
            # Jours travaillés
            expected_days_worked = 2
            self.assertEqual(contract_calc.days_worked, expected_days_worked)
            
            # Calcul du profit
            # Le service ne prend pas en compte les commissions spéciales dans le profit
            # Revenus totaux = 8 boissons * 220 THB = 1760 THB
            # Coûts totaux = 1940 THB salaire + 800 THB commission = 2740 THB
            # Profit = 1760 - 2740 = -980 THB (perte)
            expected_total_profit = -980.0
            self.assertEqual(contract_calc.total_profit, expected_total_profit)
            
            # Vérifier que l'enregistrement a été créé dans la base de données
            db_calc = ContractCalculations.query.filter_by(assignment_id=assignment.id).first()
            self.assertIsNotNone(db_calc)
            self.assertEqual(db_calc.total_salary, expected_total_salary)
            self.assertEqual(db_calc.total_commission, expected_total_commission)
            self.assertEqual(db_calc.total_profit, expected_total_profit)
            self.assertEqual(db_calc.total_drinks, expected_total_drinks)
            self.assertEqual(db_calc.total_special_comm, expected_total_special_comm)
            self.assertEqual(db_calc.days_worked, expected_days_worked)


if __name__ == '__main__':
    unittest.main()
