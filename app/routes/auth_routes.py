"""
Rôle du fichier:
Gère les endpoints d'authentification (inscription, connexion, profil courant, changement de mot de passe).
"""

from pydantic import ValidationError

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required
from flask_jwt_extended import get_jwt_identity

from app.models import User
from app.schemas.payloads import ChangePasswordSchema, LoginSchema, UserRegisterSchema
from app.services.auth_service import AuthService
from app.utils.activity_logger import log_activity


auth_bp = Blueprint("auth", __name__)


def _account_holder_payload(user: User | None) -> dict:
    """Construit le nom et la fonction du titulaire du compte."""
    if not user:
        return {
            "account_holder_name": "Utilisateur",
            "account_holder_function": "Fonction non définie",
        }

    if user.employee:
        first_name = (user.employee.first_name or "").strip()
        last_name = (user.employee.last_name or "").strip()
        full_name = f"{first_name} {last_name}".strip()
        function_name = (user.employee.role.name if user.employee.role else "") or (user.role.name if user.role else "")
        return {
            "account_holder_name": full_name or user.username,
            "account_holder_function": function_name or "Fonction non définie",
        }

    return {
        "account_holder_name": user.username,
        "account_holder_function": (user.role.name if user.role else "") or "Fonction non définie",
    }


@auth_bp.post("/register")
def register():
    """Crée un nouvel utilisateur à partir du payload d'inscription."""
    try:
        payload = UserRegisterSchema.model_validate(request.get_json() or {})
        user = AuthService.register_user(payload.username, payload.password, payload.role_name)
        log_activity(user.username, "Inscription utilisateur")
        return jsonify({"id": user.id, "username": user.username}), 201
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@auth_bp.post("/login")
def login():
    """Authentifie un utilisateur et retourne son token d'accès + profil de session."""
    try:
        payload = LoginSchema.model_validate(request.get_json() or {})
        token, user = AuthService.authenticate(payload.username, payload.password)
        log_activity(user.username, "Connexion")
        permissions = [permission.name for permission in user.role.permissions]
        holder = _account_holder_payload(user)
        return jsonify(
            {
                "access_token": token,
                "username": user.username,
                "role": user.role.name,
                "permissions": permissions,
                "must_change_password": user.must_change_password,
                "account_holder_name": holder["account_holder_name"],
                "account_holder_function": holder["account_holder_function"],
            }
        )
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@auth_bp.get("/me")
@jwt_required()
def me():
    """Retourne les claims du token JWT de l'utilisateur connecté."""
    claims = get_jwt()
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    holder = _account_holder_payload(user)

    if user and user.role:
        permissions = [permission.name for permission in user.role.permissions]
        role_name = user.role.name
        username = user.username
        must_change_password = user.must_change_password
    else:
        permissions = claims.get("permissions", [])
        role_name = claims.get("role")
        username = claims.get("username")
        must_change_password = claims.get("must_change_password", False)

    return jsonify(
        {
            "username": username,
            "role": role_name,
            "permissions": permissions,
            "must_change_password": must_change_password,
            "account_holder_name": holder["account_holder_name"],
            "account_holder_function": holder["account_holder_function"],
        }
    )


@auth_bp.post("/change-password")
@jwt_required()
def change_password():
    """Permet à l'utilisateur connecté de changer son mot de passe."""
    try:
        payload = ChangePasswordSchema.model_validate(request.get_json() or {})
        user_id = int(get_jwt_identity())
        user = AuthService.change_password(user_id, payload.current_password, payload.new_password)
        new_token, _ = AuthService.authenticate(user.username, payload.new_password)
        log_activity(user.username, "Changement mot de passe")
        return jsonify(
            {
                "message": "Mot de passe mis à jour",
                "must_change_password": user.must_change_password,
                "access_token": new_token,
            }
        )
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422
