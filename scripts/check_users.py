#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import create_app, db
from app.models import User, Agency

def check_users():
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("🔍 VÉRIFICATION DES UTILISATEURS DANS LA BASE DE DONNÉES")
        print("=" * 60)
        
        # Vérifier les agences
        agencies = Agency.query.all()
        print(f"📊 Nombre d'agences trouvées : {len(agencies)}")
        for agency in agencies:
            print(f"  - Agence ID {agency.id}: {agency.name}")
        
        print()
        
        # Vérifier tous les utilisateurs
        users = User.query.all()
        print(f"👥 Nombre d'utilisateurs trouvés : {len(users)}")
        
        if users:
            print("\n📋 Liste des utilisateurs disponibles :")
            print("-" * 50)
            for user in users:
                agency_name = user.agency.name if user.agency else "Aucune agence"
                print(f"  ID: {user.id} | Username: {user.username} | Rôle: {user.role} | Agence: {agency_name}")
        else:
            print("❌ Aucun utilisateur trouvé dans la base de données")
        
        print("\n" + "=" * 60)
        print("✅ Vérification terminée")
        print("=" * 60)

if __name__ == '__main__':
    check_users()
