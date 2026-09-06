"""Pydantic modeli za registraciju i prijavu."""

from typing import Annotated

from pydantic import BaseModel, EmailStr, StringConstraints

from backend.app.schemas.user import UserOut

Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=50),
]

# Gornja granica je bcrypt limit od 72 bajta - duze lozinke bi se tiho sekle.
Password = Annotated[str, StringConstraints(min_length=8, max_length=72)]


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
