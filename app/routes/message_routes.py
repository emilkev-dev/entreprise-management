"""
Rôle du fichier:
Expose les endpoints de messagerie interne (conversations, messages, lecture, édition, suppression).
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from pydantic import ValidationError

from app.schemas.payloads import AgentMessageCreateSchema, ChatThreadMessageSchema, MessageUpdateSchema
from app.services.enterprise_service import EnterpriseService
from app.utils.activity_logger import log_activity
from app.utils.serializers import message_to_dict


message_bp = Blueprint("messages", __name__)


def _serialize_message_for_user(message, user_id: int) -> dict:
    """Sérialise un message et ajoute les droits d'édition/suppression temporels."""
    payload = message_to_dict(message)
    remaining_seconds = EnterpriseService.message_action_remaining_seconds(user_id, message)
    can_manage = remaining_seconds > 0
    payload["can_edit"] = can_manage
    payload["can_delete"] = can_manage
    payload["edit_delete_remaining_seconds"] = remaining_seconds
    payload["edit_delete_window_minutes"] = EnterpriseService.message_edit_window_minutes()
    return payload


@message_bp.get("/recipients")
@jwt_required()
def list_recipients():
    """Retourne les destinataires potentiels pour la messagerie interne."""
    user_id = int(get_jwt_identity())
    recipients = EnterpriseService.list_message_recipients(user_id)
    return jsonify(recipients)


@message_bp.get("")
@jwt_required()
def list_inbox():
    """Retourne la boîte de réception de l'utilisateur connecté."""
    user_id = int(get_jwt_identity())
    limit = int(request.args.get("limit", 100) or 100)
    messages = EnterpriseService.list_inbox(user_id, limit=limit)
    return jsonify([_serialize_message_for_user(message, user_id) for message in messages])


@message_bp.get("/sent")
@jwt_required()
def list_sent():
    """Retourne les messages envoyés par l'utilisateur connecté."""
    user_id = int(get_jwt_identity())
    limit = int(request.args.get("limit", 100) or 100)
    messages = EnterpriseService.list_sent_messages(user_id, limit=limit)
    return jsonify([_serialize_message_for_user(message, user_id) for message in messages])


@message_bp.get("/unread-count")
@jwt_required()
def unread_count():
    """Retourne le nombre de messages non lus."""
    user_id = int(get_jwt_identity())
    count = EnterpriseService.count_unread_messages(user_id)
    return jsonify({"unread_count": count})


@message_bp.get("/conversations")
@jwt_required()
def list_conversations():
    """Retourne la liste des conversations (avec recherche optionnelle)."""
    user_id = int(get_jwt_identity())
    query = (request.args.get("q") or "").strip()
    conversations = EnterpriseService.list_conversations(user_id, query=query)
    return jsonify(conversations)


@message_bp.get("/thread/<int:other_user_id>")
@jwt_required()
def get_thread(other_user_id: int):
    """Retourne le fil de discussion avec un utilisateur donné."""
    user_id = int(get_jwt_identity())
    limit = int(request.args.get("limit", 200) or 200)
    before_id = request.args.get("before_id")
    parsed_before_id = int(before_id) if before_id and str(before_id).isdigit() else None
    EnterpriseService.mark_thread_as_read(user_id, other_user_id)
    messages = EnterpriseService.list_thread_messages(
        user_id,
        other_user_id,
        limit=limit,
        before_id=parsed_before_id,
    )
    return jsonify([_serialize_message_for_user(message, user_id) for message in messages])


@message_bp.post("/thread/<int:other_user_id>")
@jwt_required()
def send_thread_message(other_user_id: int):
    """Envoie un message dans un fil de discussion."""
    try:
        user_id = int(get_jwt_identity())
        payload = ChatThreadMessageSchema.model_validate(request.get_json() or {})
        message = EnterpriseService.send_thread_message(
            sender_user_id=user_id,
            other_user_id=other_user_id,
            content=payload.content,
            subject=payload.subject,
        )
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Envoi message thread #{message.id}")
        return jsonify(_serialize_message_for_user(message, user_id)), 201
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@message_bp.post("")
@jwt_required()
def send_message():
    """Envoie un message en mode classique (payload complet)."""
    try:
        payload = AgentMessageCreateSchema.model_validate(request.get_json() or {})
        user_id = int(get_jwt_identity())
        message = EnterpriseService.send_message(user_id, payload.model_dump())
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Envoi message interne #{message.id}")
        return jsonify(_serialize_message_for_user(message, user_id)), 201
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@message_bp.patch("/<int:message_id>/read")
@jwt_required()
def mark_read(message_id: int):
    """Marque un message comme lu."""
    user_id = int(get_jwt_identity())
    message = EnterpriseService.mark_message_as_read(user_id, message_id)
    claims = get_jwt()
    log_activity(claims.get("username", "unknown"), f"Lecture message interne #{message.id}")
    return jsonify(_serialize_message_for_user(message, user_id))


@message_bp.patch("/<int:message_id>")
@jwt_required()
def update_message(message_id: int):
    """Modifie un message envoyé, dans la fenêtre de temps autorisée."""
    try:
        user_id = int(get_jwt_identity())
        payload = MessageUpdateSchema.model_validate(request.get_json() or {})
        message = EnterpriseService.update_own_message(user_id, message_id, payload.content)
        claims = get_jwt()
        log_activity(claims.get("username", "unknown"), f"Modification message interne #{message.id}")
        return jsonify(_serialize_message_for_user(message, user_id))
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 422


@message_bp.delete("/<int:message_id>")
@jwt_required()
def delete_message(message_id: int):
    """Supprime un message envoyé, dans la fenêtre de temps autorisée."""
    user_id = int(get_jwt_identity())
    deleted_id = EnterpriseService.delete_own_message(user_id, message_id)
    claims = get_jwt()
    log_activity(claims.get("username", "unknown"), f"Suppression message interne #{deleted_id}")
    return jsonify({"message": "Message supprimé", "id": deleted_id})
