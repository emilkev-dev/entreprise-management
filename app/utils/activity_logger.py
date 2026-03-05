"""
Rôle du fichier:
Enregistre les actions importantes des utilisateurs dans l'historique d'activité.
"""

from app.extensions import db
from app.models import ActivityLog


def log_activity(username: str, action: str) -> None:
    """Persiste une action utilisateur dans la table ActivityLog."""
    record = ActivityLog(username=username, action=action)
    db.session.add(record)
    db.session.commit()
