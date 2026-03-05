"""
Rôle du fichier:
Déclare les routes UI qui servent les templates HTML.
"""

from flask import Blueprint, render_template


ui_bp = Blueprint("ui", __name__)


@ui_bp.get("/dashboard")
def dashboard_page():
    """Sert la page dashboard principale côté navigateur."""
    return render_template("dashboard.html")
