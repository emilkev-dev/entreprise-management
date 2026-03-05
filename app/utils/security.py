"""
Rôle du fichier:
Gère le hash et la vérification sécurisée des mots de passe.
"""

import bcrypt


def hash_password(password: str) -> str:
    """Hash un mot de passe en bcrypt avec salt aléatoire."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Vérifie qu'un mot de passe correspond au hash bcrypt stocké."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
