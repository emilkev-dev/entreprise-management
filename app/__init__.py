"""
Rôle du fichier:
Crée et configure l'application Flask (factory pattern),
enregistre les blueprints, initialise la base de données et prépare les handlers d'erreurs.
"""

import os

from flask import Flask, jsonify, render_template, request
from pydantic import ValidationError
from sqlalchemy import inspect, text

from app.config import Config
from app.exceptions import AppException
from app.extensions import db, jwt
from app.models import User
from app.routes import register_blueprints
from app.services.auth_service import seed_rbac


def _ensure_backward_compatible_schema() -> None:
    """Ajoute les colonnes manquantes pour garder la compatibilité avec des bases plus anciennes."""
    inspector = inspect(db.engine)

    if "employees" in inspector.get_table_names():
        employee_columns = {column["name"] for column in inspector.get_columns("employees")}
        if "matricule" not in employee_columns:
            db.session.execute(text("ALTER TABLE employees ADD COLUMN matricule VARCHAR(40)"))

    if "users" in inspector.get_table_names():
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "must_change_password" not in user_columns:
            db.session.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT 1"))
        if "employee_id" not in user_columns:
            db.session.execute(text("ALTER TABLE users ADD COLUMN employee_id INTEGER"))

    if "messages" in inspector.get_table_names():
        message_columns = {column["name"] for column in inspector.get_columns("messages")}
        if "edited_at" not in message_columns:
            db.session.execute(text("ALTER TABLE messages ADD COLUMN edited_at DATETIME"))

    if "leaves" in inspector.get_table_names():
        leave_columns = {column["name"] for column in inspector.get_columns("leaves")}
        if "decision_comment" not in leave_columns:
            db.session.execute(text("ALTER TABLE leaves ADD COLUMN decision_comment VARCHAR(500)"))

    db.session.commit()


def create_app() -> Flask:
    """Construit, configure et retourne l'instance Flask complète de l'application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["PAYSLIP_FOLDER"], exist_ok=True)

    db.init_app(app)
    jwt.init_app(app)

    register_blueprints(app)

    @app.get("/api/health")
    def health_check():
        """Endpoint de santé utilisé pour vérifier que l'API est démarrée."""
        return jsonify({"status": "ok", "service": "enterprise-management"})

    @app.get("/")
    def home():
        """Redirige vers l'interface dashboard principale."""
        return render_template("dashboard.html")

    @app.get("/api")
    def api_root():
        """Expose un point d'entrée descriptif des modules API disponibles."""
        return jsonify(
            {
                "message": "API root",
                "health": "/api/health",
                "modules": [
                    "/api/auth",
                    "/api/employees",
                    "/api/departments",
                    "/api/roles",
                    "/api/payrolls",
                    "/api/attendances",
                    "/api/leaves",
                    "/api/contracts",
                    "/api/reports",
                    "/api/messages",
                ],
            }
        )

    @app.get("/dashboard")
    def dashboard():
        """Route explicite pour servir la page dashboard."""
        return render_template("dashboard.html")

    @app.errorhandler(AppException)
    def handle_app_exception(error: AppException):
        """Transforme une exception métier en réponse JSON standardisée."""
        return jsonify({"error": error.message}), error.status_code

    @app.errorhandler(ValidationError)
    def handle_pydantic_validation_error(error: ValidationError):
        """Retourne les détails de validation Pydantic au format JSON."""
        return jsonify({"error": error.errors()}), 422

    @app.errorhandler(404)
    def not_found(_error):
        """Gère les routes inconnues avec un message explicite."""
        return jsonify({"error": "Ressource introuvable", "path": request.path, "method": request.method}), 404

    @app.errorhandler(500)
    def internal_error(_error):
        """Gère les erreurs serveur inattendues sans exposer de détails sensibles."""
        return jsonify({"error": "Erreur interne serveur"}), 500

    with app.app_context():
        db.create_all()
        _ensure_backward_compatible_schema()
        seed_rbac()
        superadmin = User.query.filter_by(username="superadmin").first()
        if superadmin and superadmin.must_change_password:
            superadmin.must_change_password = False
            db.session.commit()

    return app
