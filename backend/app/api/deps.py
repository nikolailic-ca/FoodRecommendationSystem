"""Zajednicke FastAPI zavisnosti (baza i trenutni korisnik).

Sve zavisnosti se koriste preko Annotated aliasa (DbSession, CurrentUser, ...)
umesto `= Depends(...)` u podrazumevanoj vrednosti argumenta.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.core.security import credentials_error, decode_access_token
from backend.app.db.models import User
from backend.app.db.session import get_db

# auto_error=False: nedostatak tokena resavamo sami, da bi opcione rute
# (npr. detalj recepta) mogle da rade i bez prijave.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
BearerToken = Annotated[str | None, Depends(oauth2_scheme)]


def get_current_user(db: DbSession, token: BearerToken) -> User:
    """Obavezna autentikacija: vraca ORM korisnika ili podize 401."""
    if not token:
        raise credentials_error("Potrebna je prijava.")

    user = db.get(User, decode_access_token(token))
    if user is None:
        # Token je ispravan, ali korisnik je u medjuvremenu obrisan.
        raise credentials_error("Korisnik iz tokena ne postoji.")

    return user


def get_current_user_optional(db: DbSession, token: BearerToken) -> User | None:
    """Opciona autentikacija: bez tokena vraca None.

    Ako je token poslat ali je neispravan ili istekao, i dalje se vraca 401 -
    frontend tako zna da mora da osvezi prijavu, umesto da tiho vidi
    odjavljeni prikaz sa praznim ocenama.
    """
    if not token:
        return None

    return db.get(User, decode_access_token(token))


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
