"""
Rôle du fichier:
Définit les exceptions métier personnalisées utilisées par les services et routes API.
"""

class AppException(Exception):
    """Exception de base applicative transportant un message et un code HTTP."""
    status_code = 400

    def __init__(self, message: str, status_code: int | None = None):
        """Initialise l'erreur avec un message lisible et un code optionnel."""
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


class ValidationException(AppException):
    """Erreur de validation métier ou de payload (HTTP 422)."""
    status_code = 422


class NotFoundException(AppException):
    """Erreur ressource introuvable (HTTP 404)."""
    status_code = 404


class UnauthorizedException(AppException):
    """Erreur d'authentification (HTTP 401)."""
    status_code = 401


class ForbiddenException(AppException):
    """Erreur d'autorisation insuffisante (HTTP 403)."""
    status_code = 403
