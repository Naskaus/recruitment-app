#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import create_app, db
from app.models import User, Agency

def create_admin_user():
    app = create_app()
    
    with app.app_context():
        # Vérifier si l'agence existe, sinon la créer
        agency = Agency.query.filter_by(name='Bangkok Agency').first()
        if not agency:
            agency = Agency(name='Bangkok Agency')
            db.session.add(agency)
            db.session.commit()
            print(f"Agence créée: {agency.name} (ID: {agency.id})")
        
        # Vérifier si l'utilisateur admin existe déjà
        existing_user = User.query.filter_by(username='admin').first()
        if existing_user:
            print(f"L'utilisateur 'admin' existe déjà (ID: {existing_user.id})")
            return
        
        # Créer l'utilisateur admin
        user = User(
            username='admin',
            role='super_admin',
            agency_id=agency.id
        )
        user.set_password('admin123')
        
        db.session.add(user)
        db.session.commit()
        
        print(f"Utilisateur admin créé avec succès:")
        print(f"  - Username: admin")
        print(f"  - Password: admin123")
        print(f"  - Rôle: {user.role}")
        print(f"  - Agence: {agency.name}")
        print(f"  - ID: {user.id}")

if __name__ == '__main__':
    create_admin_user()
