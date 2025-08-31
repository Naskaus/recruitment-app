# config.py
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration shared by all environments."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-default-secret-key-for-emergency'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 # 2 Megabytes

class DevelopmentConfig(Config):
    """Configuration for development."""
    DEBUG = True
    # Use local PostgreSQL database 'ok' cloned from production
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'postgresql://postgres:sEb%401217@localhost:5432/ok'
    # Activer le logging SQL pour diagnostiquer les problèmes de performance
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    """Configuration for production."""
    DEBUG = False
    # This will read the DATABASE_URL from the production environment (e.g., Heroku)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)


# A dictionary to easily access the config classes by name
config_by_name = dict(
    development=DevelopmentConfig,
    production=ProductionConfig
)