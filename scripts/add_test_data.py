#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import date, datetime, timedelta
from app import create_app, db
from app.models import (
    User, Agency, StaffProfile, Venue, AgencyPosition, AgencyContract,
    Assignment, PerformanceRecord
)

def add_test_data():
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("📊 AJOUT DE DONNÉES DE TEST COMPLÈTES")
        print("=" * 60)
        
        # Récupérer l'agence existante
        agency = Agency.query.filter_by(name='Bangkok Agency').first()
        if not agency:
            print("❌ Agence Bangkok Agency non trouvée")
            return
        
        print(f"🏢 Utilisation de l'agence : {agency.name}")
        
        # Récupérer les positions existantes
        positions = AgencyPosition.query.filter_by(agency_id=agency.id).all()
        print(f"📋 Positions disponibles : {[p.name for p in positions]}")
        
        # Récupérer les venues existantes
        venues = Venue.query.filter_by(agency_id=agency.id).all()
        print(f"🏪 Venues disponibles : {[v.name for v in venues]}")
        
        # Récupérer les contrats existants
        contracts = AgencyContract.query.filter_by(agency_id=agency.id).all()
        print(f"📄 Contrats disponibles : {[c.name for c in contracts]}")
        
        # 1. Créer des profils de staff
        staff_data = [
            {
                'staff_id': 'ST001',
                'first_name': 'Sophie',
                'last_name': 'Chen',
                'nickname': 'Sophie',
                'phone': '+66 81 234 5678',
                'instagram': '@sophie_chen',
                'facebook': 'sophie.chen.123',
                'line_id': 'sophie_chen',
                'dob': date(1995, 6, 15),
                'height': 165,
                'weight': 50,
                'status': 'active',
                'preferred_position': 'Dancer',
                'admin_mama_name': 'Mama Lisa',
                'notes': 'Excellente danseuse, très professionnelle'
            },
            {
                'staff_id': 'ST002',
                'first_name': 'Maya',
                'last_name': 'Rodriguez',
                'nickname': 'Maya',
                'phone': '+66 82 345 6789',
                'instagram': '@maya_rodriguez',
                'facebook': 'maya.rodriguez.456',
                'line_id': 'maya_rodriguez',
                'dob': date(1993, 9, 22),
                'height': 170,
                'weight': 55,
                'status': 'active',
                'preferred_position': 'Hostess',
                'admin_mama_name': 'Mama Lisa',
                'notes': 'Très bonne hôtesse, parle bien anglais'
            },
            {
                'staff_id': 'ST003',
                'first_name': 'Yuki',
                'last_name': 'Tanaka',
                'nickname': 'Yuki',
                'phone': '+66 83 456 7890',
                'instagram': '@yuki_tanaka',
                'facebook': 'yuki.tanaka.789',
                'line_id': 'yuki_tanaka',
                'dob': date(1997, 3, 8),
                'height': 160,
                'weight': 48,
                'status': 'active',
                'preferred_position': 'Dancer',
                'admin_mama_name': 'Mama Lisa',
                'notes': 'Danseuse talentueuse, très populaire'
            },
            {
                'staff_id': 'ST004',
                'first_name': 'Emma',
                'last_name': 'Wilson',
                'nickname': 'Emma',
                'phone': '+66 84 567 8901',
                'instagram': '@emma_wilson',
                'facebook': 'emma.wilson.012',
                'line_id': 'emma_wilson',
                'dob': date(1994, 12, 3),
                'height': 168,
                'weight': 52,
                'status': 'active',
                'preferred_position': 'Hostess',
                'admin_mama_name': 'Mama Lisa',
                'notes': 'Hôtesse expérimentée, parle français'
            }
        ]
        
        created_staff = []
        for staff_info in staff_data:
            existing_staff = StaffProfile.query.filter_by(staff_id=staff_info['staff_id'], agency_id=agency.id).first()
            if not existing_staff:
                staff = StaffProfile(
                    agency_id=agency.id,
                    **staff_info
                )
                db.session.add(staff)
                created_staff.append(staff)
                print(f"👤 Staff créé : {staff.first_name} {staff.last_name} ({staff.staff_id})")
            else:
                created_staff.append(existing_staff)
                print(f"👤 Staff existant : {existing_staff.first_name} {existing_staff.last_name}")
        
        db.session.commit()
        
        # 2. Créer des assignments (contrats de payroll)
        user = User.query.filter_by(username='Seb').first()
        
        # Dates pour les assignments
        today = date.today()
        
        assignment_data = [
            {
                'staff_id': created_staff[0].id,  # Sophie
                'venue_id': venues[0].id,  # Red Dragon
                'contract_role': 'Dancer',
                'contract_type': '1day',
                'start_date': today + timedelta(days=1),
                'end_date': today + timedelta(days=1),
                'base_salary': 2000,
                'status': 'active'
            },
            {
                'staff_id': created_staff[1].id,  # Maya
                'venue_id': venues[1].id,  # Mandarin
                'contract_role': 'Hostess',
                'contract_type': '10days',
                'start_date': today + timedelta(days=2),
                'end_date': today + timedelta(days=11),
                'base_salary': 15000,
                'status': 'active'
            },
            {
                'staff_id': created_staff[2].id,  # Yuki
                'venue_id': venues[2].id,  # Shark
                'contract_role': 'Dancer',
                'contract_type': '1month',
                'start_date': today + timedelta(days=3),
                'end_date': today + timedelta(days=32),
                'base_salary': 45000,
                'status': 'active'
            },
            {
                'staff_id': created_staff[3].id,  # Emma
                'venue_id': venues[0].id,  # Red Dragon
                'contract_role': 'Hostess',
                'contract_type': '1day',
                'start_date': today - timedelta(days=5),
                'end_date': today - timedelta(days=5),
                'base_salary': 2000,
                'status': 'ended'
            }
        ]
        
        created_assignments = []
        for assignment_info in assignment_data:
            assignment = Assignment(
                agency_id=agency.id,
                managed_by_user_id=user.id,
                **assignment_info
            )
            db.session.add(assignment)
            created_assignments.append(assignment)
            
            # Récupérer le staff pour l'affichage
            staff = StaffProfile.query.get(assignment_info['staff_id'])
            venue = Venue.query.get(assignment_info['venue_id'])
            print(f"📋 Assignment créé : {staff.first_name} {staff.last_name} - {venue.name} ({assignment.contract_type})")
        
        db.session.commit()
        
        # 3. Créer des performance records
        performance_data = [
            {
                'assignment_id': created_assignments[0].id,
                'record_date': today + timedelta(days=1),
                'drinks_sold': 8,
                'daily_salary': 2000,
                'daily_profit': 1600
            },
            {
                'assignment_id': created_assignments[1].id,
                'record_date': today + timedelta(days=2),
                'drinks_sold': 12,
                'daily_salary': 1500,
                'daily_profit': 2400
            },
            {
                'assignment_id': created_assignments[2].id,
                'record_date': today + timedelta(days=3),
                'drinks_sold': 15,
                'daily_salary': 1500,
                'daily_profit': 3000
            }
        ]
        
        for perf_info in performance_data:
            performance = PerformanceRecord(**perf_info)
            db.session.add(performance)
            
            # Récupérer l'assignment pour l'affichage
            assignment = Assignment.query.get(perf_info['assignment_id'])
            staff = StaffProfile.query.get(assignment.staff_id)
            print(f"📊 Performance créée : {staff.first_name} {staff.last_name} - {perf_info['drinks_sold']} boissons")
        
        db.session.commit()
        
        print("\n" + "=" * 60)
        print("✅ DONNÉES DE TEST AJOUTÉES AVEC SUCCÈS !")
        print("=" * 60)
        print(f"👥 Staff créé : {len(created_staff)} profils")
        print(f"📋 Assignments créés : {len(created_assignments)} contrats")
        print(f"📊 Performances créées : {len(performance_data)} enregistrements")
        print("=" * 60)
        print("🚀 Vous pouvez maintenant voir :")
        print("  - Les profils de staff dans /staff/")
        print("  - Les assignments dans /dispatch/")
        print("  - Les calculs de payroll dans /payroll/")
        print("=" * 60)

if __name__ == '__main__':
    add_test_data()
