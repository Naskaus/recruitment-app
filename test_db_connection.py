#!/usr/bin/env python3
"""
Script de test pour vérifier la connexion à la base de données PostgreSQL
"""

import os
import sys
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

def test_postgresql_connection():
    """Teste la connexion à PostgreSQL"""
    print("🔍 Test de connexion à PostgreSQL...")
    
    # Vérifier si la variable d'environnement est définie
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ ERREUR: Variable DATABASE_URL non trouvée dans .env")
        print("   Assurez-vous que le fichier .env contient:")
        print('   DATABASE_URL="postgresql://postgres:sEb%401217@localhost:5432/os_agency_prod_replica"')
        return False
    
    print(f"✅ Variable DATABASE_URL trouvée: {database_url[:50]}...")
    
    # Tester l'import de psycopg2
    try:
        import psycopg2
        print("✅ psycopg2 importé avec succès")
    except ImportError:
        print("❌ ERREUR: psycopg2 non installé")
        print("   Installez-le avec: pip install psycopg2-binary")
        print("   Ou décommentez la ligne dans requirements.txt:")
        print("   #psycopg2-binary==2.9.9")
        return False
    
    # Tester la connexion
    try:
        print("🔌 Tentative de connexion à PostgreSQL...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Test simple
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Connexion réussie!")
        print(f"   Version PostgreSQL: {version[0]}")
        
        # Tester les tables principales
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        if tables:
            print(f"✅ {len(tables)} tables trouvées:")
            for table in tables[:10]:  # Afficher les 10 premières
                print(f"   - {table[0]}")
            if len(tables) > 10:
                print(f"   ... et {len(tables) - 10} autres")
        else:
            print("⚠️  Aucune table trouvée dans la base de données")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.OperationalError as e:
        print(f"❌ ERREUR de connexion: {e}")
        print("\n🔧 Solutions possibles:")
        print("   1. Vérifiez que PostgreSQL est démarré")
        print("   2. Vérifiez les paramètres de connexion dans .env")
        print("   3. Vérifiez que la base 'os_agency_prod_replica' existe")
        return False
    except Exception as e:
        print(f"❌ ERREUR inattendue: {e}")
        return False

def test_flask_config():
    """Teste la configuration Flask"""
    print("\n🔍 Test de la configuration Flask...")
    
    try:
        from config import DevelopmentConfig, ProductionConfig
        
        # Test de la configuration de développement
        dev_config = DevelopmentConfig()
        print(f"✅ Configuration de développement chargée")
        print(f"   DEBUG: {dev_config.DEBUG}")
        print(f"   SQLALCHEMY_ECHO: {dev_config.SQLALCHEMY_ECHO}")
        
        # Test de la configuration de production
        prod_config = ProductionConfig()
        print(f"✅ Configuration de production chargée")
        print(f"   DATABASE_URL: {prod_config.SQLALCHEMY_DATABASE_URI[:50]}..." if prod_config.SQLALCHEMY_DATABASE_URI else "   DATABASE_URL: Non défini")
        
        return True
        
    except Exception as e:
        print(f"❌ ERREUR de configuration Flask: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 Test de configuration de la base de données")
    print("=" * 50)
    
    # Test de la configuration Flask
    flask_ok = test_flask_config()
    
    # Test de la connexion PostgreSQL
    postgres_ok = test_postgresql_connection()
    
    print("\n" + "=" * 50)
    if flask_ok and postgres_ok:
        print("🎉 TOUS LES TESTS RÉUSSIS!")
        print("   Votre application peut maintenant utiliser PostgreSQL")
    else:
        print("⚠️  Certains tests ont échoué")
        print("   Vérifiez les erreurs ci-dessus")

if __name__ == "__main__":
    main()
