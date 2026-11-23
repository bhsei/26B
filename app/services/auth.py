import hashlib
import re
import secrets
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import monotonic

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.auth_schemas import normalize_email
from app.config import Settings
from app.errors import AppError
from app.models import AuthSession, User, utc_now

PASSWORDS = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    email: str
    csrf_token: str
    token_hash: str


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_password(password: str, encoded: str) -> bool:
    try:
        return PASSWORDS.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def new_password_hash(password: str) -> str:
    if len(password) < 12 or len(password) > 1024:
        raise ValueError("Use a password of 12 to 1024 characters.")
    return PASSWORDS.hash(password)


def create_user(email: str, password: str, sessions: sessionmaker) -> User:
    email = normalize_email(email)
    encoded = new_password_hash(password)
    with sessions() as db:
        user = User(email=email, password_hash=encoded)
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValueError("An account with this email already exists.") from None
        return user


class LoginLimiter:
    """Bounded, per-process IP limit. A public deployment also needs proxy limits."""

    def __init__(self, settings: Settings):
        self.limit = settings.auth_login_max_attempts
        self.window = settings.auth_login_window_seconds
        self.entries = OrderedDict()
        self.lock = Lock()

    def check(self, address: str) -> None:
        now = monotonic()
        with self.lock:
            start, count = self.entries.pop(address, (now, 0))
            if now - start >= self.window:
                start, count = now, 0
            self.entries[address] = (start, count + 1)
            while len(self.entries) > 4096:
                self.entries.popitem(last=False)
            if count >= self.limit:
                retry = max(1, int(self.window - (now - start)) + 1)
                raise AppError(
                    429,
                    "Too many sign-in attempts. Try again later.",
                    "LOGIN_RATE_LIMITED",
                    headers={"Retry-After": str(retry)},
                )


def login(email: str, password: str, sessions: sessionmaker, settings: Settings):
    # Release the connection before the relatively expensive password hash check.
    with sessions() as db:
        user = db.scalar(select(User).where(User.email == email))
        credentials = (user.id, user.email, user.password_hash, user.is_active) if user else None
    encoded = credentials[2] if credentials else DUMMY_HASH
    valid = verify_password(password, encoded)
    if not valid or credentials is None or not credentials[3]:
        raise AppError(401, "Invalid email or password.", "INVALID_CREDENTIALS")

    raw_token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = utc_now()
    with sessions() as db:
        # Recheck after hashing: an administrator may have disabled/reset the account.
        active = db.scalar(select(User).where(User.id == credentials[0], User.is_active.is_(True)))
        if active is None or active.password_hash != encoded:
            raise AppError(401, "Invalid email or password.", "INVALID_CREDENTIALS")
        db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
        db.add(
            AuthSession(
                token_hash=token_hash(raw_token),
                user_id=active.id,
                csrf_token=csrf,
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(seconds=settings.auth_session_ttl_seconds),
            )
        )
        if PASSWORDS.check_needs_rehash(encoded):
            active.password_hash = PASSWORDS.hash(password)
        db.commit()
    return raw_token, AuthContext(credentials[0], credentials[1], csrf, token_hash(raw_token))


def authenticate(raw_token: str | None, sessions: sessionmaker, settings: Settings) -> AuthContext:
    if raw_token is None or not TOKEN_PATTERN.fullmatch(raw_token):
        raise AppError(401, "Sign in to continue.", "AUTHENTICATION_REQUIRED")
    key = token_hash(raw_token)
    now = utc_now()
    with sessions() as db:
        row = db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.token_hash == key)
        ).first()
        if row is None:
            raise AppError(401, "Sign in to continue.", "AUTHENTICATION_REQUIRED")
        session, user = row
        if (
            not user.is_active
            or utc(session.expires_at) <= now
            or utc(session.last_seen_at) + timedelta(seconds=settings.auth_session_idle_seconds)
            <= now
        ):
            db.delete(session)
            db.commit()
            raise AppError(401, "Your session has ended. Sign in again.", "SESSION_EXPIRED")
        result = AuthContext(user.id, user.email, session.csrf_token, key)
        # Avoid a write on every read. The SQL session still closes before generation.
        if utc(session.last_seen_at) < now - timedelta(seconds=30):
            db.execute(
                update(AuthSession).where(AuthSession.token_hash == key).values(last_seen_at=now)
            )
            db.commit()
    return result


def logout(key: str, sessions: sessionmaker) -> None:
    with sessions() as db:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == key))
        db.commit()
