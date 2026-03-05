"""
Rôle du fichier:
Déclare les extensions Flask partagées (SQLAlchemy et JWT) réutilisées dans toute l'application.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager


db = SQLAlchemy()
jwt = JWTManager()
