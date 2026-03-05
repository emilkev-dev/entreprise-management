"""
Rôle du fichier:
Contient la logique métier d'authentification, de gestion des comptes et l'initialisation RBAC.
"""

from flask import current_app
from flask_jwt_extended import create_access_token
from sqlalchemy import func, or_

from app.exceptions import NotFoundException, UnauthorizedException, ValidationException
from app.extensions import db
from app.models import Employee, EmployeeStatus, Permission, Role, User
from app.utils.security import hash_password, verify_password


def _is_active_employee_status(status: str | None) -> bool:
    """Normalise un statut et indique s'il correspond à un employé actif."""
    normalized = (status or "").strip().lower()
    return normalized in {"actif", "act", "active"}


class AuthService:
    """Service d'authentification et de gestion des comptes utilisateurs."""

    @staticmethod
    def register_user(username: str, password: str, role_name: str) -> User:
        """Crée un compte utilisateur en vérifiant l'unicité du login et l'existence du rôle."""
        existing = User.query.filter_by(username=username).first()
        if existing:
            raise ValidationException("Nom d'utilisateur déjà utilisé")

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            raise NotFoundException("Rôle introuvable")

        user = User(
            username=username,
            password_hash=hash_password(password),
            role_id=role.id,
            must_change_password=False,
        )
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def authenticate(username: str, password: str) -> tuple[str, User]:
        """Authentifie un utilisateur puis génère un JWT enrichi des claims métier."""
        login_identifier = (username or "").strip()
        if not login_identifier:
            raise UnauthorizedException("Identifiants invalides")

        normalized_identifier = login_identifier.lower()
        user = (
            User.query.outerjoin(Employee, User.employee_id == Employee.id)
            .filter(
                or_(
                    func.lower(User.username) == normalized_identifier,
                    func.lower(Employee.matricule) == normalized_identifier,
                    func.lower(Employee.email) == normalized_identifier,
                )
            )
            .first()
        )
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedException("Identifiants invalides")

        if user.employee and not _is_active_employee_status(user.employee.status):
            raise UnauthorizedException("Compte agent non actif")

        permissions = [p.name for p in user.role.permissions]
        token = create_access_token(
            identity=str(user.id),
            additional_claims={
                "username": user.username,
                "role": user.role.name,
                "permissions": permissions,
                "must_change_password": user.must_change_password,
            },
        )
        return token, user

    @staticmethod
    def change_password(user_id: int, current_password: str, new_password: str) -> User:
        """Met à jour le mot de passe d'un compte après contrôle des identifiants."""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("Utilisateur introuvable")

        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedException("Mot de passe actuel invalide")

        if current_password == new_password:
            raise ValidationException("Le nouveau mot de passe doit être différent")

        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        db.session.commit()
        return user

    @staticmethod
    def list_agent_accounts() -> list[User]:
        """Retourne la liste des comptes agents triés du plus récent au plus ancien."""
        return User.query.order_by(User.id.desc()).all()

    @staticmethod
    def reset_agent_password(user_id: int) -> User:
        """Réinitialise le mot de passe d'un agent avec le mot de passe par défaut."""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("Compte introuvable")

        default_password = current_app.config.get("DEFAULT_AGENT_PASSWORD", "Agent@123")
        user.password_hash = hash_password(default_password)
        user.must_change_password = True
        db.session.commit()
        return user

    @staticmethod
    def update_agent_role(user_id: int, role_id: int) -> User:
        """Change le rôle d'un compte utilisateur et synchronise l'employé lié si présent."""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("Compte introuvable")

        role = Role.query.get(role_id)
        if not role:
            raise NotFoundException("Rôle introuvable")

        user.role_id = role.id
        if user.employee:
            user.employee.role_id = role.id
        db.session.commit()
        return user

    @staticmethod
    def update_agent_status(user_id: int, status: str) -> User:
        """Met à jour le statut RH de l'agent rattaché au compte."""
        user = User.query.get(user_id)
        if not user:
            raise NotFoundException("Compte introuvable")

        if status not in {EmployeeStatus.ACTIVE.value, EmployeeStatus.SUSPENDED.value, EmployeeStatus.RESIGNED.value}:
            raise ValidationException("Statut invalide")

        if not user.employee:
            raise ValidationException("Ce compte n'est pas lié à un agent")

        user.employee.status = status
        db.session.commit()
        return user


def seed_rbac() -> None:
    """Initialise permissions et rôles par défaut au démarrage de l'application."""
    permissions = [
        "Voir employés",
        "Modifier employés",
        "Voir salaires",
        "Exporter rapports",
        "Valider congés",
        "Voir comptabilité",
        # Manager / team-level permissions
        "Voir équipe",
        "Valider congés équipe",
        "Attribuer tâches",
        "Gérer objectifs",
        "Gérer évaluations",
        "Voir performances",
        "Exporter rapports équipe",
    ]

    for name in permissions:
        if not Permission.query.filter_by(name=name).first():
            db.session.add(Permission(name=name))
    db.session.commit()

    role_map = {
        "SuperAdmin": permissions,
        "Admin RH": ["Voir employés", "Modifier employés", "Voir salaires", "Exporter rapports", "Valider congés"],
        "Manager": [
            "Voir employés",
            "Voir équipe",
            "Voir salaires",
            "Valider congés équipe",
            "Attribuer tâches",
            "Voir performances",
            "Exporter rapports équipe",
        ],
        "Employé": ["Voir employés"],
        "RH": ["Voir employés", "Modifier employés", "Valider congés"],
        "Comptable": ["Voir employés", "Voir salaires", "Exporter rapports", "Voir comptabilité"],
        "Comptable Junior": ["Voir employés", "Voir salaires", "Voir comptabilité"],
        "Comptable Senior": ["Voir employés", "Voir salaires", "Exporter rapports", "Voir comptabilité"],
        "Chef Comptable": ["Voir employés", "Voir salaires", "Exporter rapports", "Voir comptabilité"],
        "Chef Département": ["Voir employés", "Valider congés"],
        "Stagiaire": ["Voir employés"],
        "Auditeur": ["Voir employés", "Voir salaires", "Exporter rapports"],
        "Coordinateur RH": ["Voir employés", "Modifier employés", "Valider congés"],
        "Contrôleur Paie": ["Voir employés", "Voir salaires", "Exporter rapports"],
        "Superviseur": ["Voir employés", "Valider congés"],
        "Analyste RH": ["Voir employés", "Exporter rapports"],
    }

    for role_name, perms in role_map.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name)
            db.session.add(role)
            db.session.flush()

        permission_entities = Permission.query.filter(Permission.name.in_(perms)).all()
        role.permissions = permission_entities

    db.session.commit()
