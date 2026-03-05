"""
Rôle du fichier:
Centralise la configuration de l'application (base de données, JWT, uploads, paramètres globaux).
"""

import os
from datetime import timedelta


class Config:
    """Configuration centrale lue au démarrage de l'application Flask."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me-please-use-env-var-32chars")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-me-please-use-env-var-32chars")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///enterprise.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads/contracts")
    PAYSLIP_FOLDER = os.getenv("PAYSLIP_FOLDER", "uploads/payslips")
    DEFAULT_AGENT_PASSWORD = os.getenv("DEFAULT_AGENT_PASSWORD", "Agent@123")
    MESSAGE_EDIT_DELETE_WINDOW_MINUTES = int(os.getenv("MESSAGE_EDIT_DELETE_WINDOW_MINUTES", "15"))
