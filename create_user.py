#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import create_app, db
from app.models import User, Agency

def create_user():
    app = create_app()
    
    with app.app_context():
        # Vérifier si l'agence existe, sinon la créer
        agency = Agency.query.filter_by(name='Bangkok Agency').first()
        if not agency:
            agency = Agency(name='Bangkok Agency')
            db.session.add(agency)
            db.session.commit()
            print(f"Agence créée: {agency.name} (ID: {agency.id})")
        
        # Vérifier si l'utilisateur existe déjà
        existing_user = User.query.filter_by(username='Seb').first()
        if existing_user:
            print(f"L'utilisateur 'Seb' existe déjà (ID: {existing_user.id})")
            return
        
        # Créer l'utilisateur
        user = User(
            username='Seb',
            role='webdev',
            agency_id=agency.id
        )
        user.set_password('sEb@1217')
        
        db.session.add(user)
        db.session.commit()
        
        print(f"Utilisateur créé avec succès:")
        print(f"  - Username: {user.username}")
        print(f"  - Rôle: {user.role}")
        print(f"  - Agence: {agency.name}")
        print(f"  - ID: {user.id}")

if __name__ == '__main__':
    create_user()
