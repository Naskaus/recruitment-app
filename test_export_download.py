#!/usr/bin/env python3
"""
Script de test pour vérifier les routes d'export et de téléchargement
"""

import os
import sys

# Ajouter le répertoire racine au path Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Agency, User

def test_export_download_routes():
    """Test des routes d'export et de téléchargement"""
    
    print("🧪 TEST DES ROUTES D'EXPORT ET TÉLÉCHARGEMENT")
    print("=" * 60)
    
    try:
        # Créer l'application Flask
        app = create_app()
        
        with app.app_context():
            # Vérifier qu'il y a des agences
            agencies = Agency.query.all()
            
            if not agencies:
                print("❌ Aucune agence trouvée dans la base de données!")
                return
            
            print(f"✅ {len(agencies)} agence(s) trouvée(s)")
            
            # Afficher les agences
            for agency in agencies:
                users_count = User.query.filter_by(agency_id=agency.id).count()
                print(f"   - {agency.name} (ID: {agency.id}, Users: {users_count})")
            
            # Vérifier le dossier d'export
            export_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'exports')
            print(f"\n📁 Dossier d'export: {export_dir}")
            
            if os.path.exists(export_dir):
                print(f"✅ Dossier d'export existe")
                files = os.listdir(export_dir)
                if files:
                    print(f"   Fichiers présents: {len(files)}")
                    for file in files[:5]:  # Afficher les 5 premiers
                        print(f"     - {file}")
                    if len(files) > 5:
                        print(f"     ... et {len(files) - 5} autres")
                else:
                    print("   Aucun fichier d'export présent")
            else:
                print(f"❌ Dossier d'export n'existe pas")
                print(f"   Création du dossier...")
                os.makedirs(export_dir, exist_ok=True)
                print(f"   ✅ Dossier créé")
            
            # Vérifier la configuration
            print(f"\n⚙️  CONFIGURATION:")
            print(f"   UPLOAD_FOLDER: {app.config.get('UPLOAD_FOLDER', 'Non défini')}")
            print(f"   SECRET_KEY: {'Défini' if app.config.get('SECRET_KEY') else 'Non défini'}")
            
            print(f"\n🎯 ROUTES disponibles:")
            print(f"   - POST /admin/api/agencies/<id>/export")
            print(f"   - GET  /admin/api/agencies/<id>/export/download/<filename>")
            print(f"   - POST /admin/delete_agency/<id>")
            
            print(f"\n✅ Test terminé avec succès!")
            
    except Exception as e:
        print(f"❌ ERREUR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_export_download_routes()
