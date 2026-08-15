from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=30)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class UserOut(ORMModel):
    id: int
    email: EmailStr
    first_name: str | None
    last_name: str | None
    phone: str | None
    profile_photo_path: str | None
    company_id: int | None
    is_active: bool
    is_email_verified: bool
    last_login_at: datetime | None


class MeResponse(BaseModel):
    user: UserOut
    roles: list[str]
    permissions: list[str]
    company_id: int | None
    company_name: str | None = None
    is_onboarded: bool = False
    onboarding_step: str | None = None
    employee_id: int | None = None
    # True for a platform-level executive, who picks which company to view.
    is_executive: bool = False


class AuthResponse(BaseModel):
    user: UserOut
    roles: list[str]
    tokens: TokenPair
    # Present only while no mailer is wired; lets you verify without an inbox.
    email_verification_token: str | None = None
