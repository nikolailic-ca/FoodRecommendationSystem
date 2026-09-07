"""Pydantic modeli za registraciju i prijavu."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, StringConstraints

from backend.app.core.security import BCRYPT_MAX_BYTES
from backend.app.schemas.user import UserOut

Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=50),
]


def _within_bcrypt_limit(value: str) -> str:
    """bcrypt meri BAJTOVE, ne karaktere.

    Sama duzina stringa je propustala lozinku od 72 visebajtna karaktera (do 288
    bajtova), koju bi hesiranje potom tiho odseklo na 72 bajta - korisnik bi
    dobio nalog sa lozinkom koju nikada nije ukucao.
    """
    if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"Password must be at most {BCRYPT_MAX_BYTES} bytes long. "
            "Accented and non-Latin characters count as more than one byte."
        )
    return value


# max_length je brza provera koja odbija ocigledno preduge unose; validator
# ispod hvata slucaj kada je karaktera <= 72 a bajtova vise.
Password = Annotated[
    str,
    StringConstraints(min_length=8, max_length=BCRYPT_MAX_BYTES),
    AfterValidator(_within_bcrypt_limit),
]


class RegisterRequest(BaseModel):
    username: Username
    email: EmailStr
    password: Password


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterResponse(TokenResponse):
    """Registracija odmah vraca token da frontend moze da posalje
    onboarding ocene bez dodatne prijave."""

    user: UserOut
