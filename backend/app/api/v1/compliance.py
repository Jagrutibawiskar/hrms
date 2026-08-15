from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import Perm
from app.core.rbac import P
from app.models.compliance import CompanyCompliance
from app.schemas.compliance import (
    ComplianceCheck,
    ComplianceOut,
    ComplianceStatus,
    ComplianceUpdate,
)
from app.services import company_service, notification_service

router = APIRouter(prefix="/compliance", tags=["Compliance"])

ReadAccess = Perm(P.COMPANY_READ)
ManageAccess = Perm(P.SETTINGS_MANAGE, P.ORG_MANAGE)


def get_or_create(db, company_id: int) -> CompanyCompliance:
    """Every company gets a compliance record on first read, with Indian defaults."""
    record = db.scalar(
        select(CompanyCompliance).where(CompanyCompliance.company_id == company_id)
    )
    if record is None:
        company = company_service.get_company(db, company_id)
        record = CompanyCompliance(company_id=company_id, pt_state=company.state)
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


@router.get("", response_model=ComplianceOut)
def get_compliance(principal: ReadAccess):
    return get_or_create(principal.db, principal.tenant_id)


@router.put("", response_model=ComplianceOut)
def update_compliance(payload: ComplianceUpdate, principal: ManageAccess):
    record = get_or_create(principal.db, principal.tenant_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(record, field, value)

    notification_service.audit(
        principal.db,
        company_id=principal.tenant_id,
        user_id=principal.user_id,
        action="compliance.update",
        entity_type="company_compliance",
        entity_id=record.id,
        changes=changes,
    )
    principal.db.commit()
    principal.db.refresh(record)
    return record


@router.get("/status", response_model=ComplianceStatus)
def compliance_status(principal: ReadAccess):
    """Readiness checklist — what still needs filling in before payroll is compliant."""
    record = get_or_create(principal.db, principal.tenant_id)
    company = company_service.get_company(principal.db, principal.tenant_id)

    checks = [
        ComplianceCheck(
            label="Company PAN",
            ok=bool(record.pan),
            detail=record.pan or "Not set — required for TDS filings.",
        ),
        ComplianceCheck(
            label="Provident Fund",
            ok=not record.pf_enabled or bool(record.pf_number),
            detail=(
                "Disabled for this company."
                if not record.pf_enabled
                else record.pf_number or "PF is enabled but no establishment code is set."
            ),
        ),
        ComplianceCheck(
            label="Employee State Insurance",
            ok=not record.esi_enabled or bool(record.esi_number),
            detail=(
                "Disabled for this company."
                if not record.esi_enabled
                else record.esi_number or "ESI is enabled but no code is set."
            ),
        ),
        ComplianceCheck(
            label="Professional Tax",
            ok=not record.pt_enabled or bool(record.pt_state),
            detail=(
                "Disabled for this company."
                if not record.pt_enabled
                else f"{record.pt_state} · {record.pt_monthly_amount}/month"
                if record.pt_state
                else "PT is enabled but no state is selected."
            ),
        ),
        ComplianceCheck(
            label="TDS (TAN)",
            ok=not record.tds_enabled or bool(record.tan),
            detail=(
                "TDS deduction is off."
                if not record.tds_enabled
                else record.tan or "TDS is enabled but no TAN is set."
            ),
        ),
        ComplianceCheck(
            label="Registered address",
            ok=bool(company.address and company.postal_code),
            detail=f"{company.city}, {company.state} {company.postal_code}"
            if company.address
            else "Incomplete.",
        ),
    ]
    return ComplianceStatus(ready=all(c.ok for c in checks), checks=checks)
