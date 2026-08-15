from fastapi import APIRouter, Request, status
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, client_ip
from app.core.exceptions import Unauthorized
from app.core.rbac import permissions_for_roles
from app.core.security import REFRESH_TOKEN, decode_token
from app.models.company import Company
from app.models.employee import Employee
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenPair,
    UserOut,
    VerifyEmailRequest,
)
from app.schemas.common import Message
from app.services import auth_service, notification_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: DbSession, request: Request):
    user = auth_service.signup(db, payload)
    token = user.email_verification_token
    notification_service.audit(
        db,
        company_id=None,
        user_id=user.id,
        action="auth.signup",
        entity_type="user",
        entity_id=user.id,
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return AuthResponse(
        user=UserOut.model_validate(user),
        roles=user.role_names,
        tokens=TokenPair(**auth_service.issue_tokens(user)),
        email_verification_token=token if settings.DEBUG else None,
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: DbSession, request: Request):
    user = auth_service.authenticate(db, payload.email, payload.password)
    notification_service.audit(
        db,
        company_id=user.company_id,
        user_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return AuthResponse(
        user=UserOut.model_validate(user),
        roles=user.role_names,
        tokens=TokenPair(**auth_service.issue_tokens(user)),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: DbSession):
    try:
        claims = decode_token(payload.refresh_token)
    except Exception:
        raise Unauthorized("Invalid or expired refresh token")
    if claims.get("type") != REFRESH_TOKEN:
        raise Unauthorized("Not a refresh token")

    user = db.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise Unauthorized("User no longer active")
    return TokenPair(**auth_service.issue_tokens(user))


@router.post("/logout", response_model=Message)
def logout(principal: CurrentUser):
    """Stateless JWT: the client discards the tokens. Recorded for the audit trail."""
    notification_service.audit(
        principal.db,
        company_id=principal.company_id,
        user_id=principal.user_id,
        action="auth.logout",
        entity_type="user",
        entity_id=principal.user_id,
    )
    principal.db.commit()
    return Message(message="Logged out")


@router.get("/me", response_model=MeResponse)
def me(principal: CurrentUser):
    user = principal.user
    # An executive viewing a company should see that company's context, not their own.
    company_id = principal.viewing_company_id or user.company_id
    company = principal.db.get(Company, company_id) if company_id else None
    employee = principal.db.scalar(select(Employee).where(Employee.user_id == user.id))
    return MeResponse(
        user=UserOut.model_validate(user),
        roles=user.role_names,
        permissions=sorted(permissions_for_roles(user.role_names)),
        company_id=company_id,
        company_name=company.name if company else None,
        # An executive is never held at the onboarding gate.
        is_onboarded=company.is_onboarded if company else principal.is_executive,
        onboarding_step=company.onboarding_step.value if company else None,
        employee_id=employee.id if employee else None,
        is_executive=principal.is_executive,
    )


@router.post("/verify-email", response_model=Message)
def verify_email(payload: VerifyEmailRequest, db: DbSession):
    auth_service.verify_email(db, payload.token)
    db.commit()
    return Message(message="Email verified successfully")


@router.post("/forgot-password", response_model=Message)
def forgot_password(payload: ForgotPasswordRequest, db: DbSession):
    token = auth_service.start_password_reset(db, payload.email)
    db.commit()
    message = "If an account exists for that email, a reset link has been sent."
    if settings.DEBUG and token:
        # No mailer in MVP-1; expose the token in dev so the flow is testable.
        return Message(message=f"{message} [dev token: {token}]")
    return Message(message=message)


@router.post("/reset-password", response_model=Message)
def reset_password(payload: ResetPasswordRequest, db: DbSession):
    auth_service.reset_password(db, payload.token, payload.new_password)
    db.commit()
    return Message(message="Password reset successfully")


@router.post("/change-password", response_model=Message)
def change_password(payload: ChangePasswordRequest, principal: CurrentUser):
    auth_service.change_password(
        principal.db, principal.user, payload.current_password, payload.new_password
    )
    principal.db.commit()
    return Message(message="Password changed successfully")
