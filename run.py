"""
Rôle du fichier:
Point d'entrée principal de l'application Flask.
Ce script gère le verrou d'exécution, vérifie le port et lance le serveur web.
"""

import os
import sys
import socket
import urllib.request
import urllib.error
import json
import atexit


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

LOCK_FILE = os.path.join(BASE_DIR, ".run.lock")
_LOCK_ACQUIRED = False


def _is_debug_enabled() -> bool:
    """Retourne True si le mode debug est activé via variables d'environnement."""
    return os.getenv("FLASK_DEBUG", "0") == "1" or os.getenv("APP_DEBUG", "0") == "1"


def _read_port() -> int:
    """Lit le port depuis PORT et applique une valeur par défaut sûre (5000)."""
    raw_port = os.getenv("PORT", "5000")
    try:
        return int(raw_port)
    except ValueError:
        return 5000


def _is_port_open(host: str, port: int) -> bool:
    """Teste rapidement si un port TCP est déjà occupé sur l'hôte ciblé."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.6)
        return sock.connect_ex((host, port)) == 0


def _is_our_service_running(host: str, port: int) -> bool:
    """Vérifie si le service déjà présent sur le port correspond bien à cette application."""
    url = f"http://{host}:{port}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("service") == "enterprise-management" and payload.get("status") == "ok"
    except (urllib.error.URLError, ValueError, TimeoutError):
        return False


def _is_pid_running(pid: int) -> bool:
    """Indique si un PID système est encore actif."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _release_lock() -> None:
    """Libère le fichier de verrou pour autoriser un prochain lancement."""
    global _LOCK_ACQUIRED
    if _LOCK_ACQUIRED and os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass
    _LOCK_ACQUIRED = False


def _acquire_lock() -> bool:
    """Crée un verrou de processus unique afin d'éviter les doubles exécutions."""
    global _LOCK_ACQUIRED

    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as lock_reader:
                existing_pid = int((lock_reader.read() or "0").strip() or "0")
            if existing_pid and _is_pid_running(existing_pid):
                return False
        except (OSError, ValueError):
            pass

        try:
            os.remove(LOCK_FILE)
        except OSError:
            return False

    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as lock_writer:
            lock_writer.write(str(os.getpid()))
        _LOCK_ACQUIRED = True
        return True
    except FileExistsError:
        return False


if __name__ == "__main__":
    atexit.register(_release_lock)
    try:
        from app import create_app

        if not _acquire_lock():
            print("Instance déjà active détectée. Aucun nouveau serveur lancé.")
            sys.exit(0)

        app = create_app()
        debug_mode = _is_debug_enabled()
        host = os.getenv("HOST", "127.0.0.1")
        port = _read_port()

        if _is_port_open(host, port):
            if _is_our_service_running(host, port):
                print(f"Instance déjà active sur http://{host}:{port}. Aucun nouveau serveur lancé.")
                sys.exit(0)

            print(f"Le port {port} est déjà utilisé par un autre processus.")
            print("Libère le port ou définis un autre PORT avant de relancer.")
            sys.exit(1)

        print(f"Lancement du serveur sur http://{host}:{port}")
        app.run(host=host, port=port, debug=debug_mode, use_reloader=False)
    except KeyboardInterrupt:
        print("Serveur arrêté manuellement (Ctrl+C). Ce n'est pas une erreur.")
    finally:
        _release_lock()
