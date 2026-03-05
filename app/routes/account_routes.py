"""
Rôle du fichier:
Expose les endpoints d'administration des comptes agents (rôles, statuts, reset mot de passe, historique d'activité).
"""

import csv
from datetime import datetime
from io import BytesIO, StringIO

from flask import Blueprint, Response, jsonify, request, send_file
from flask_jwt_extended import get_jwt, jwt_required
from pydantic import ValidationError
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.models import ActivityLog
from app.schemas.payloads import AccountRoleUpdateSchema, AccountStatusUpdateSchema
from app.services.auth_service import AuthService
from app.utils.activity_logger import log_activity
from app.utils.rbac import permission_required


account_bp = Blueprint("accounts", __name__)


def _is_admin_role() -> bool:
    """Vérifie si le rôle courant est autorisé à gérer les comptes agents."""
    claims = get_jwt()
    return claims.get("role") in {"SuperAdmin", "Admin RH", "RH"}


def _build_activity_logs_query():
    """Construit dynamiquement une requête filtrée sur l'historique d'activité."""
    query = ActivityLog.query

    username = (request.args.get("username") or "").strip()
    action = (request.args.get("action") or "").strip()
    start_date = (request.args.get("start_date") or "").strip()
    end_date = (request.args.get("end_date") or "").strip()

    if username:
        query = query.filter(ActivityLog.username.ilike(f"%{username}%"))

    if action:
        query = query.filter(ActivityLog.action.ilike(f"%{action}%"))

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(ActivityLog.created_at >= start_dt)
        except ValueError as exc:
            raise ValidationError.from_exception_data(
                "ActivityLogsFilter",
                [
                    {
                        "type": "value_error",
                        "loc": ("start_date",),
                        "msg": "Format start_date invalide (YYYY-MM-DD)",
                        "input": start_date,
                    }
                ],
            ) from exc

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            query = query.filter(ActivityLog.created_at <= end_dt)
        except ValueError as exc:
            raise ValidationError.from_exception_data(
                "ActivityLogsFilter",
                [
                    {
                        "type": "value_error",
                        "loc": ("end_date",),
                        "msg": "Format end_date invalide (YYYY-MM-DD)",
                        "input": end_date,
                    }
                ],
            ) from exc

    return query


def _serialize_log(log: ActivityLog):
    """Convertit un enregistrement d'activité en dictionnaire JSON."""
    return {
        "id": log.id,
        "username": log.username,
        "action": log.action,
        "created_at": log.created_at.isoformat(),
    }


@account_bp.get("")
@jwt_required()
@permission_required("Modifier employés")
def list_accounts():
    """Liste les comptes agents avec leurs métadonnées RH."""
    if not _is_admin_role():
        return jsonify({"error": "Accès interdit"}), 403

    users = AuthService.list_agent_accounts()
    result = []
    for user in users:
        employee = user.employee
        result.append(
            {
                "id": user.id,
                "username": user.username,
                "role_id": user.role_id,
                "role": user.role.name if user.role else None,
                "must_change_password": user.must_change_password,
                "employee_id": employee.id if employee else None,
                "employee_name": f"{employee.first_name} {employee.last_name}" if employee else None,
                "matricule": employee.matricule if employee else None,
                "status": employee.status if employee else None,
            }
        )
    return jsonify(result)


@account_bp.patch("/<int:user_id>/reset-password")
@jwt_required()
@permission_required("Modifier employés")
def reset_password(user_id: int):
    """Réinitialise le mot de passe d'un compte agent."""
    if not _is_admin_role():
        return jsonify({"error": "Accès interdit"}), 403

    user = AuthService.reset_agent_password(user_id)
    claims = get_jwt()
    log_activity(claims.get("username", "unknown"), f"Reset mot de passe compte #{user.id}")
    return jsonify({"message": "Mot de passe réinitialisé", "user_id": user.id, "must_change_password": user.must_change_password})


@account_bp.patch("/<int:user_id>/role")
@jwt_required()
@permission_required("Modifier employés")
def update_role(user_id: int):
    """Modifie le rôle d'un compte agent."""
    if not _is_admin_role():
        return jsonify({"error": "Accès interdit"}), 403

    try:
        payload = AccountRoleUpdateSchema.model_validate(request.get_json() or {})
        user = AuthService.update_agent_role(user_id, payload.role_id)
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Changement rôle compte #{user.id} -> role #{payload.role_id}")
        return jsonify({"message": "Rôle mis à jour", "user_id": user.id, "role": user.role.name if user.role else None})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@account_bp.patch("/<int:user_id>/status")
@jwt_required()
@permission_required("Modifier employés")
def update_status(user_id: int):
    """Modifie le statut RH lié à un compte agent."""
    if not _is_admin_role():
        return jsonify({"error": "Accès interdit"}), 403

    try:
        payload = AccountStatusUpdateSchema.model_validate(request.get_json() or {})
        user = AuthService.update_agent_status(user_id, payload.status)
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Changement statut compte #{user.id} -> {payload.status}")
        return jsonify({"message": "Statut mis à jour", "user_id": user.id, "status": user.employee.status if user.employee else None})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@account_bp.get("/activity")
@jwt_required()
@permission_required("Modifier employés")
def list_activity_logs():
    """Retourne la liste des logs d'activité avec filtres optionnels."""
    if not _is_admin_role():
        return jsonify({"error": "Accès interdit"}), 403

    try:
        query = _build_activity_logs_query()
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422

    logs = query.order_by(ActivityLog.created_at.desc()).limit(200).all()
    return jsonify([_serialize_log(log) for log in logs])


@account_bp.get("/activity/export.csv")
@jwt_required()
@permission_required("Modifier employés")
def export_activity_logs_csv():
    """Exporte l'historique d'activité au format CSV."""
    if not _is_admin_role():
        return jsonify({"error": "Accès interdit"}), 403

    try:
        query = _build_activity_logs_query()
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422

    logs = query.order_by(ActivityLog.created_at.desc()).limit(1000).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "username", "action", "created_at"])
    for log in logs:
        writer.writerow([log.id, log.username, log.action, log.created_at.isoformat()])

    filename = f"activity_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@account_bp.get("/activity/export.pdf")
@jwt_required()
@permission_required("Modifier employés")
def export_activity_logs_pdf():
    """Exporte l'historique d'activité au format PDF."""
    if not _is_admin_role():
        return jsonify({"error": "Accès interdit"}), 403

    try:
        query = _build_activity_logs_query()
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422

    logs = query.order_by(ActivityLog.created_at.desc()).limit(300).all()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    y = page_height - 40
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(30, y, "Historique des actions administrateur")
    y -= 24

    pdf.setFont("Helvetica", 9)
    for log in logs:
        date_label = log.created_at.strftime("%Y-%m-%d %H:%M:%S")
        row_text = f"#{log.id} | {date_label} | {log.username} | {log.action}"
        if len(row_text) > 115:
            row_text = f"{row_text[:112]}..."
        pdf.drawString(30, y, row_text)
        y -= 14

        if y < 40:
            pdf.showPage()
            pdf.setFont("Helvetica", 9)
            y = page_height - 40

    pdf.save()
    buffer.seek(0)

    filename = f"activity_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
