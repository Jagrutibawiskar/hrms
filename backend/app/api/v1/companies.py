from fastapi import APIRouter, File, UploadFile, status

from app.core.config import settings
from app.core.deps import CurrentUser, Perm
from app.core.exceptions import BadRequest, Forbidden
from app.core.rbac import P
from app.schemas.common import Message
from app.schemas.company import CompanyCreate, CompanyOut, CompanyUpdate
from app.services import company_service, notification_service
from app.utils.files import delete_file, save_upload

router = APIRouter(prefix="/companies", tags=["Company"])

ReadAccess = Perm(P.COMPANY_READ)
UpdateAccess = Perm(P.COMPANY_UPDATE)

LOGO_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/svg+xml"}


def with_logo_url(company) -> CompanyOut:
    """Adds a browser-usable URL for the stored logo path."""
    out = CompanyOut.model_validate(company, from_attributes=True)
    out.logo_url = f"{settings.STATIC_URL}/{company.logo_path}" if company.logo_path else None
    return out


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, principal: CurrentUser):
    """Creates the tenant and makes the caller its COMPANY_ADMIN.

    Also seeds a head-office location, a default work policy, the four standard
    leave types and a default salary structure.
    """
    company = company_service.create_company(principal.db, principal.user, payload)
    notification_service.audit(
        principal.db,
        company_id=company.id,
        user_id=principal.user_id,
        action="company.create",
        entity_type="company",
        entity_id=company.id,
    )
    principal.db.commit()
    principal.db.refresh(company)
    return with_logo_url(company)


@router.get("", response_model=list[CompanyOut])
def list_companies(principal: CurrentUser):
    """Every company on the platform — powers the executive's company switcher."""
    if not principal.is_executive:
        raise Forbidden("Only an executive can list companies")

    from sqlalchemy import select

    from app.models.company import Company

    rows = principal.db.scalars(select(Company).order_by(Company.name))
    return [with_logo_url(c) for c in rows]


@router.get("/current", response_model=CompanyOut)
def get_current_company(principal: ReadAccess):
    return with_logo_url(company_service.get_company(principal.db, principal.tenant_id))


@router.post("/current/logo", response_model=CompanyOut)
def upload_logo(principal: CurrentUser, file: UploadFile = File(...)):
    """Uploads the company logo, shown in the app, on payslips and on documents.

    Allowed during onboarding (before `is_onboarded`), so a new company can brand
    itself right after signup.
    """
    principal.require(P.COMPANY_UPDATE, P.ORG_MANAGE)
    if file.content_type not in LOGO_TYPES:
        raise BadRequest("Logo must be a PNG, JPEG, WEBP or SVG image")

    company = company_service.get_company(principal.db, principal.tenant_id)
    previous = company.logo_path

    path, _size = save_upload(file, f"company_{company.id}/branding")
    company.logo_path = path
    principal.db.commit()
    principal.db.refresh(company)

    if previous and previous != path:
        delete_file(previous)
    return with_logo_url(company)


@router.delete("/current/logo", response_model=Message)
def remove_logo(principal: UpdateAccess):
    company = company_service.get_company(principal.db, principal.tenant_id)
    stored = company.logo_path
    company.logo_path = None
    principal.db.commit()
    if stored:
        delete_file(stored)
    return Message(message="Logo removed")


@router.patch("/current", response_model=CompanyOut)
def update_current_company(
    payload: CompanyUpdate,
    principal: UpdateAccess,
):
    company = company_service.get_company(principal.db, principal.tenant_id)
    data = payload.model_dump(exclude_unset=True)
    if "company_size" in data and data["company_size"] is not None:
        data["company_size"] = data["company_size"].value
    if "email" in data and data["email"] is not None:
        data["email"] = str(data["email"]).lower()

    for field, value in data.items():
        setattr(company, field, value)

    notification_service.audit(
        principal.db,
        company_id=company.id,
        user_id=principal.user_id,
        action="company.update",
        entity_type="company",
        entity_id=company.id,
        changes=data,
    )
    principal.db.commit()
    principal.db.refresh(company)
    return with_logo_url(company)
