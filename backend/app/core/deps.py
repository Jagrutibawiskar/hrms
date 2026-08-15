from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import Forbidden, NotFound, Unauthorized
from app.core.rbac import permissions_for_roles
from app.core.security import ACCESS_TOKEN, decode_token
from app.models.employee import Employee, EmployeeEmploymentDetail
from app.models.enums import RoleName
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")

DbSession = Annotated[Session, Depends(get_db)]


@dataclass
class Principal:
    """The authenticated caller: identity + tenant + effective permissions."""

    user: User
    db: Session
    permissions: set[str]
    # Set only for an executive (SUPER_ADMIN) who picked a company to view.
    viewing_company_id: int | None = None

    @property
    def user_id(self) -> int:
        return self.user.id

    @property
    def company_id(self) -> int | None:
        return self.user.company_id

    @property
    def roles(self) -> list[str]:
        return self.user.role_names

    def has(self, *perms: str) -> bool:
        return any(p in self.permissions for p in perms)

    def require(self, *perms: str) -> None:
        if not self.has(*perms):
            raise Forbidden(f"Requires one of: {', '.join(perms)}")

    def has_role(self, *roles: RoleName) -> bool:
        wanted = {r.value for r in roles}
        return bool(wanted & set(self.roles))

    @property
    def is_executive(self) -> bool:
        """Platform-level account that can look into any company."""
        return self.has_role(RoleName.SUPER_ADMIN)

    @property
    def tenant_id(self) -> int:
        """Company scope for every query.

        Taken from the authenticated user, never from request input — with one
        deliberate exception: an executive may name the company they are viewing,
        and that claim is verified against their SUPER_ADMIN role before it is used.
        """
        if self.viewing_company_id is not None:
            return self.viewing_company_id
        if self.user.company_id is None:
            raise Forbidden(
                "Select a company to view."
                if self.is_executive
                else "This account is not attached to a company yet"
            )
        return self.user.company_id

    @property
    def employee(self) -> Employee | None:
        return self.db.scalar(select(Employee).where(Employee.user_id == self.user.id))

    @property
    def employee_or_404(self) -> Employee:
        emp = self.employee
        if emp is None:
            raise NotFound("No employee record is linked to this account")
        return emp

    def team_employee_ids(self) -> list[int]:
        """Direct reports of the caller, plus the caller. Used for MANAGER scoping."""
        me = self.employee
        if me is None:
            return []
        report_ids = list(
            self.db.scalars(
                select(EmployeeEmploymentDetail.employee_id).where(
                    EmployeeEmploymentDetail.manager_id == me.id
                )
            )
        )
        return [me.id, *report_ids]


def get_current_principal(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> Principal:
    if credentials is None or not credentials.credentials:
        raise Unauthorized()

    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Token has expired")
    except jwt.PyJWTError:
        raise Unauthorized("Invalid token")

    if payload.get("type") != ACCESS_TOKEN:
        raise Unauthorized("Invalid token type")

    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise Unauthorized("User no longer exists")
    if not user.is_active:
        raise Forbidden("This account has been deactivated")

    principal = Principal(user=user, db=db, permissions=permissions_for_roles(user.role_names))

    # An executive may scope the request to any company via this header. Everyone
    # else is ignored here, so a normal admin cannot reach another tenant by
    # sending it.
    requested = request.headers.get("x-company-id")
    if requested and principal.is_executive:
        from app.models.company import Company

        company = db.get(Company, int(requested)) if requested.isdigit() else None
        if company is None:
            raise NotFound("Company not found")
        principal.viewing_company_id = company.id

    request.state.principal = principal
    return principal


CurrentUser = Annotated[Principal, Depends(get_current_principal)]


def require_permissions(*perms: str):
    """Route dependency: caller must hold at least one of `perms`."""

    def _dep(principal: CurrentUser) -> Principal:
        principal.require(*perms)
        return principal

    return _dep


def Perm(*perms: str):  # noqa: N802 - used in annotation position, reads as a type
    """Annotated dependency: `principal: Perm(P.EMPLOYEE_READ_ALL)`."""
    return Annotated[Principal, Depends(require_permissions(*perms))]


def require_onboarded(principal: CurrentUser) -> Principal:
    """Blocks the main app until the company finished the onboarding wizard."""
    from app.models.company import Company

    company = principal.db.get(Company, principal.tenant_id)
    if company is None:
        raise Forbidden("Company not found")
    if not company.is_onboarded:
        raise Forbidden("Company onboarding is not complete")
    return principal


OnboardedUser = Annotated[Principal, Depends(require_onboarded)]


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
