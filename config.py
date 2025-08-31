# config.py
import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration shared by all environments."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-default-secret-key-for-emergency'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data', 'recruitment-dev.db')
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 # 2 Megabytes

class DevelopmentConfig(Config):
    """Configuration for development."""
    DEBUG = True
    # Activer le logging SQL pour diagnostiquer les problèmes de performance
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    """Configuration for production."""
    DEBUG = False


# A dictionary to easily access the config classes by name
config_by_name = dict(
    development=DevelopmentConfig,
    production=ProductionConfig
)