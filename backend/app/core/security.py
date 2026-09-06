"""Lozinke (bcrypt) i JWT tokeni (PyJWT).

Namerno se ne koristi passlib: paket je nenodrzavan i puca na Python 3.13+.
bcrypt se poziva direktno, sto je i jednostavnije i providnije.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import HTTPException, status

from backend.app.core.config import settings

JWT_ALGORITHM = "HS256"

# bcrypt hesira najvise 72 bajta ulaza; sve preko toga se tiho ignorise,
# pa lozinku secemo eksplicitno da bi hesiranje i provera radili isto.
BCRYPT_MAX_BYTES = 72

# Zaglavlje koje klijentu govori da je u pitanju Bearer autentikacija.
AUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


def credentials_error(detail: str) -> HTTPException:
    """401 sa WWW-Authenticate zaglavljem (jedno mesto za sve slucajeve)."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=AUTH_HEADERS,
    )


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Vraca bcrypt hes lozinke (60 karaktera, staje u users.password_hash)."""
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Proverava lozinku. Neispravan hes u bazi znaci "ne poklapa se", ne 500."""
    try:
        return bcrypt.checkpw(_password_bytes(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    """HS256 token sa sub/iat/exp. PyJWT >= 2.10 zahteva da 'sub' bude string."""
    issued_at = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(days=settings.jwt_expires_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Vraca user_id iz tokena ili podize 401 (istekao / neispravan token)."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise credentials_error("Token je istekao, prijavite se ponovo.") from exc
    except jwt.InvalidTokenError as exc:
        raise credentials_error("Neispravan token.") from exc

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise credentials_error("Token nema ispravan 'sub' claim.")

    try:
        return int(subject)
    except ValueError as exc:
        raise credentials_error("Token nema ispravan 'sub' claim.") from exc
