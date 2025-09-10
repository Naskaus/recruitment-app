#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

import shutil
from app import create_app, db
from app.models import User, Agency, StaffProfile, Venue, AgencyPosition, AgencyContract

def reset_and_import_db():
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("🔄 RÉINITIALISATION COMPLÈTE DE LA BASE DE DONNÉES")
        print("=" * 60)
        
        # 1. Sauvegarder l'ancienne base de données
        db_path = os.path.join(project_root, 'data', 'recruitment-dev.db')
        if os.path.exists(db_path):
            backup_name = f"recruitment_backup_{int(os.path.getmtime(db_path))}.db"
            backup_path = os.path.join(project_root, 'data', backup_name)
            shutil.copy2(db_path, backup_path)
            print(f"📦 Sauvegarde créée : {backup_path}")
        
        # 2. Supprimer la base de données actuelle
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"🗑️ Base de données supprimée : {db_path}")
        
        # 3. Créer une nouvelle base de données vide
        db.create_all()
        print("✨ Nouvelle base de données créée")
        
        # 4. Créer l'agence Bangkok Agency
        agency = Agency.query.filter_by(name='Bangkok Agency').first()
        if not agency:
            agency = Agency(name='Bangkok Agency')
            db.session.add(agency)
            db.session.commit()
            print(f"🏢 Agence créée : {agency.name} (ID: {agency.id})")
        else:
            print(f"🏢 Agence existante : {agency.name} (ID: {agency.id})")
        
        # 5. Créer l'utilisateur Seb
        existing_user = User.query.filter_by(username='Seb').first()
        if not existing_user:
            user = User(
                username='Seb',
                role='webdev',
                agency_id=agency.id
            )
            user.set_password('sEb@1217')
            db.session.add(user)
            db.session.commit()
            print(f"👤 Utilisateur créé : {user.username} (ID: {user.id})")
        else:
            print(f"👤 Utilisateur existant : {existing_user.username} (ID: {existing_user.id})")
            user = existing_user
        
        # 6. Créer quelques positions d'agence
        positions = ['Dancer', 'Hostess', 'Manager']
        for pos_name in positions:
            existing_pos = AgencyPosition.query.filter_by(name=pos_name, agency_id=agency.id).first()
            if not existing_pos:
                position = AgencyPosition(name=pos_name, agency_id=agency.id)
                db.session.add(position)
        db.session.commit()
        print(f"📋 Positions créées : {', '.join(positions)}")
        
        # 7. Créer quelques venues
        venues = ['Red Dragon', 'Mandarin', 'Shark']
        for venue_name in venues:
            existing_venue = Venue.query.filter_by(name=venue_name, agency_id=agency.id).first()
            if not existing_venue:
                venue = Venue(name=venue_name, agency_id=agency.id)
                db.session.add(venue)
        db.session.commit()
        print(f"🏪 Venues créées : {', '.join(venues)}")
        
        # 8. Créer des contrats d'agence
        contracts = [
                {'name': '1day', 'days': 1, 'drink_price': 120, 'staff_commission': 100},
    {'name': '10days', 'days': 10, 'drink_price': 120, 'staff_commission': 100},
    {'name': '1month', 'days': 30, 'drink_price': 120, 'staff_commission': 100}
        ]
        
        for contract_data in contracts:
            existing_contract = AgencyContract.query.filter_by(name=contract_data['name'], agency_id=agency.id).first()
            if not existing_contract:
                contract = AgencyContract(
                    name=contract_data['name'],
                    days=contract_data['days'],
                    drink_price=contract_data['drink_price'],
                    staff_commission=contract_data['staff_commission'],
                    agency_id=agency.id
                )
                db.session.add(contract)
        db.session.commit()
        print(f"📄 Contrats créés : {', '.join([c['name'] for c in contracts])}")
        
        print("\n" + "=" * 60)
        print("✅ Base de données réinitialisée avec succès !")
        print("=" * 60)
        print(f"👤 Utilisateur de connexion : Seb / sEb@1217")
        print(f"🏢 Agence : {agency.name}")
        print("=" * 60)

if __name__ == '__main__':
    reset_and_import_db()