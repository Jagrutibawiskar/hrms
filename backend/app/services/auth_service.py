from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BadRequest, Conflict, Forbidden, NotFound, Unauthorized
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_url_token,
    hash_password,
    verify_password,
)
from app.models.enums import RoleName
from app.models.user import Role, User, UserRole
from app.schemas.auth import SignupRequest
from app.utils.dates import utcnow


def get_role(db: Session, name: RoleName) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if role is None:
        raise NotFound(f"Role {name.value} is not seeded")
    return role


def assign_role(db: Session, user: User, name: RoleName, company_id: int | None = None) -> None:
    role = get_role(db, name)
    exists = db.scalar(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    )
    if exists:
        return
    db.add(UserRole(user_id=user.id, role_id=role.id, company_id=company_id))


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


def signup(db: Session, payload: SignupRequest) -> User:
    if get_user_by_email(db, payload.email):
        raise Conflict("An account with this email already exists")

    user = User(
        email=payload.email.strip().lower(),
        password_hash=hash_password(payload.password),
        first_name=payload.first_name.strip(),
        last_name=(payload.last_name or "").strip() or None,
        phone=payload.phone,
        is_active=True,
        is_email_verified=not settings.REQUIRE_EMAIL_VERIFICATION,
        email_verification_token=generate_url_token(),
    )
    db.add(user)
    db.flush()

    # Company-less until they create one; COMPANY_ADMIN is granted at company creation.
    assign_role(db, user, RoleName.EMPLOYEE)
    db.flush()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise Unauthorized("Incorrect email or password")
    if not user.is_active:
        raise Forbidden("This account has been deactivated")
    if settings.REQUIRE_EMAIL_VERIFICATION and not user.is_email_verified:
        raise Forbidden("Please verify your email before logging in")

    user.last_login_at = utcnow()
    return user


def issue_tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.company_id, user.role_names),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def verify_email(db: Session, token: str) -> User:
    user = db.scalar(select(User).where(User.email_verification_token == token))
    if user is None:
        raise BadRequest("Invalid or already-used verification token")
    user.is_email_verified = True
    user.email_verification_token = None
    return user


def start_password_reset(db: Session, email: str) -> str | None:
    """Returns the reset token, or None when no such account exists.

    The caller must always respond with the same message so this endpoint
    cannot be used to enumerate registered email addresses.
    """
    user = get_user_by_email(db, email)
    if user is None:
        return None
    user.password_reset_token = generate_url_token()
    user.password_reset_expires_at = utcnow() + timedelta(hours=1)
    return user.password_reset_token


def reset_password(db: Session, token: str, new_password: str) -> User:
    user = db.scalar(select(User).where(User.password_reset_token == token))
    if user is None:
        raise BadRequest("Invalid or already-used reset token")

    expires = user.password_reset_expires_at
    if expires is None:
        raise BadRequest("Invalid reset token")
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=utcnow().tzinfo)
    if expires < utcnow():
        raise BadRequest("This reset link has expired")

    user.password_hash = hash_password(new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    return user


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise BadRequest("Current password is incorrect")
    if current == new:
        raise BadRequest("New password must differ from the current password")
    user.password_hash = hash_password(new)
