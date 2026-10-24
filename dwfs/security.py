"""
Central security helpers: input validation, path confinement,
unguessable IDs, redirect validation and login throttling.
"""

import re
import secrets
import string
import time
from collections import defaultdict
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse, unquote

from flask import current_app, request, url_for
from werkzeug.utils import secure_filename

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
MIN_PASSWORD_LENGTH = 10
MAX_NAME_LENGTH = 100
UID_ALPHABET = string.ascii_letters + string.digits
UID_LENGTH = 16


class PathViolation(Exception):
    """Raised when a user supplied path would leave the permitted directory."""


def data_dir() -> Path:
    return current_app.config["DATA_DIR"]


def valid_username(username) -> bool:
    return bool(username) and bool(USERNAME_RE.fullmatch(username))


def valid_password(password) -> bool:
    return bool(password) and len(password) >= MIN_PASSWORD_LENGTH


def clean_name(name):
    """
    Normalize a user supplied file/folder/subject name. Returns None if the
    name is empty or changes under secure_filename (e.g. contains '/' or '..').
    """
    if not name:
        return None
    cleaned = secure_filename(name)
    if not cleaned or len(cleaned) > MAX_NAME_LENGTH:
        return None
    return cleaned


def is_clean_segment(segment) -> bool:
    return bool(segment) and clean_name(segment) == segment


def confine(*parts) -> Path:
    """
    Join parts below DATA_DIR and guarantee the resolved result stays inside it.
    This is the single choke point against path traversal for all disk access.
    """
    base = data_dir()
    candidate = Path(base, *parts).resolve()
    if candidate != base and base not in candidate.parents:
        raise PathViolation(str(candidate))
    return candidate


def user_subject_path(username, subject, *segments) -> Path:
    if not valid_username(username) or not is_clean_segment(subject):
        raise PathViolation(f"{username}/{subject}")
    for segment in segments:
        if not is_clean_segment(segment):
            raise PathViolation(segment)
    return confine(username, subject, *segments)


def segments_from_url(url, subject):
    """
    Extract the folder segments below /edit_subject/<subject>/ from a URL the
    client sends along. Only the path part is used, every segment is validated.
    """
    if not url:
        raise PathViolation("missing path")

    prefix = url_for("main.edit_subject", subject=subject).rstrip("/")
    path = unquote(urlparse(url).path).rstrip("/")

    if path != prefix and not path.startswith(prefix + "/"):
        raise PathViolation(path)

    segments = [s for s in path[len(prefix):].split("/") if s]
    for segment in segments:
        if not is_clean_segment(segment):
            raise PathViolation(segment)
    return segments


def generate_uid(existing=()) -> str:
    """Cryptographically secure, unguessable ID (used in share/download links)."""
    while True:
        uid = "".join(secrets.choice(UID_ALPHABET) for _ in range(UID_LENGTH))
        if uid not in existing:
            return uid


def safe_redirect_target(target, fallback):
    """Only allow redirects to paths on this host (prevents open redirects)."""
    if target:
        parsed = urlparse(target)
        if (not parsed.netloc or parsed.netloc == request.host) and parsed.path.startswith("/") \
                and not parsed.path.startswith("//"):
            return parsed.path + (f"?{parsed.query}" if parsed.query else "")
    return fallback


class LoginThrottle:
    """
    Simple in-memory brute force protection: after MAX_ATTEMPTS failed logins
    for a (client IP, username) pair, further attempts are blocked for WINDOW seconds.
    """

    MAX_ATTEMPTS = 5
    WINDOW = 15 * 60

    def __init__(self):
        self._failures = defaultdict(list)
        self._lock = Lock()

    def _key(self, username):
        return (request.remote_addr, (username or "").lower())

    def _recent(self, key):
        now = time.monotonic()
        self._failures[key] = [t for t in self._failures[key] if now - t < self.WINDOW]
        return self._failures[key]

    def is_blocked(self, username) -> bool:
        with self._lock:
            return len(self._recent(self._key(username))) >= self.MAX_ATTEMPTS

    def fail(self, username):
        with self._lock:
            self._recent(self._key(username)).append(time.monotonic())

    def reset(self, username):
        with self._lock:
            self._failures.pop(self._key(username), None)


login_throttle = LoginThrottle()
