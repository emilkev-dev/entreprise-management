"""
Rôle du fichier:
Fournit les décorateurs de contrôle d'accès basés sur les permissions JWT (RBAC).
"""

from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request


def permission_required(permission_name: str):
    """Décorateur Flask qui impose la présence d'une permission dans le JWT."""
    def decorator(fn):
        """Enveloppe une route pour y appliquer le contrôle d'accès."""
        @wraps(fn)
        def wrapper(*args, **kwargs):
            """Vérifie token, statut de mot de passe et permission avant exécution."""
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("must_change_password", False):
                return jsonify({"error": "Changement de mot de passe requis"}), 403
            permissions = claims.get("permissions", [])
            if permission_name not in permissions:
                return jsonify({"error": "Accès interdit"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
