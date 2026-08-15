"""HR employee lifecycle: the add-employee wizard, bank/statutory records,
document policy, document verification and the document dashboard.

The wizard is deliberately step-by-step and saves as it goes, because HR rarely
has everything at once. An employee starts as DRAFT and only becomes COMPLETE
when the company's document policy is satisfied.
"""

from datetime import date

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.core.deps import CurrentUser, Perm
from app.core.exceptions import BadRequest, Conflict, NotFound
from app.core.pagination import Page, Pagination, build_page, paginate
from app.core.rbac import P
from app.models.company import Company
from app.models.document import EmployeeDocument
from app.models.employee import Employee
from app.models.enums import DocumentStatus, DocumentType, NotificationEvent, ProfileStatus
from app.models.onboarding_records import (
    DocumentPolicy,
    EmployeeBankDetail,
    EmployeeStatutoryDetail,
)
from app.schemas.common import Message
from app.schemas.hr import (
    BankOut,
    BankStep,
    ContactStep,
    DocumentChecklist,
    DocumentDashboard,
    DocumentKpis,
    DocumentPolicyOut,
    DocumentPolicyUpdate,
    DocumentReject,
    DocumentVerify,
    DraftEmployeeCreate,
    EmployeeReview,
    EmploymentStep,
    PersonalStep,
    StatutoryOut,
    StatutoryStep,
)
from app.schemas.misc import DocumentOut
from app.services import company_service, hr_service, leave_service, notification_service
from app.utils.dates import today, utcnow

router = APIRouter(prefix="/hr", tags=["HR"])

ReadAccess = Perm(P.EMPLOYEE_READ_ALL)
ManageAccess = Perm(P.EMPLOYEE_CREATE)
DocAccess = Perm(P.DOCUMENT_MANAGE)
SalaryAccess = Perm(P.SALARY_READ)


def _employee(principal, employee_id: int) -> Employee:
    return hr_service.require_employee(principal.db, principal.tenant_id, employee_id)


# ---------------------------------------------------------------- employee code


@router.get("/employee-code/preview", response_model=list[str])
def preview_codes(principal: ManageAccess, count: int = Query(3, ge=1, le=10)):
    """What the next auto-generated employee codes will look like."""
    company = company_service.get_company(principal.db, principal.tenant_id)
    return hr_service.preview_employee_codes(company, count)


# ---------------------------------------------------------------- wizard


@router.post("/employees/draft", status_code=status.HTTP_201_CREATED)
def start_employee(payload: DraftEmployeeCreate, principal: ManageAccess):
    """Step 0 — creates the DRAFT record the rest of the wizard fills in."""
    db, tenant = principal.db, principal.tenant_id
    company = company_service.get_company(db, tenant)
    work_email = str(payload.work_email).strip().lower()

    if db.scalar(
        select(Employee.id).where(
            Employee.company_id == tenant, Employee.work_email == work_email
        )
    ):
        raise Conflict(f"An employee with email {work_email} already exists")

    code = (payload.employee_code or "").strip() or hr_service.generate_employee_code(db, company)
    if db.scalar(
        select(Employee.id).where(
            Employee.company_id == tenant, Employee.employee_code == code
        )
    ):
        raise Conflict(f"Employee code {code} is already in use")

    employee = Employee(
        company_id=tenant,
        employee_code=code,
        first_name=payload.first_name.strip(),
        middle_name=(payload.middle_name or "").strip() or None,
        last_name=(payload.last_name or "").strip() or None,
        work_email=work_email,
        profile_status=ProfileStatus.DRAFT,
    )
    db.add(employee)
    db.flush()

    hr_service.ensure_personal(db, employee)
    hr_service.ensure_employment(db, employee, payload.joining_date or today())

    notification_service.audit(
        db, company_id=tenant, user_id=principal.user_id,
        action="employee.draft_created", entity_type="employee", entity_id=employee.id,
        changes={"employee_code": code},
    )
    db.commit()
    db.refresh(employee)
    return {
        "employee_id": employee.id,
        "employee_code": employee.employee_code,
        "profile_status": employee.profile_status.value,
        "next_step": "personal",
    }


@router.patch("/employees/{employee_id}/personal", response_model=Message)
def save_personal(employee_id: int, payload: PersonalStep, principal: ManageAccess):
    """Step 1."""
    employee = _employee(principal, employee_id)
    data = payload.model_dump(exclude_unset=True)

    for field in ("first_name", "middle_name", "last_name"):
        if field in data:
            setattr(employee, field, data.pop(field) or None)

    personal = hr_service.ensure_personal(principal.db, employee)
    for field, value in data.items():
        setattr(personal, field, value)

    principal.db.commit()
    return Message(message="Personal details saved")


@router.patch("/employees/{employee_id}/contact", response_model=Message)
def save_contact(employee_id: int, payload: ContactStep, principal: ManageAccess):
    """Step 2."""
    employee = _employee(principal, employee_id)
    personal = hr_service.ensure_personal(principal.db, employee)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(personal, field, str(value) if field == "personal_email" and value else value)

    principal.db.commit()
    return Message(message="Contact details saved")


@router.patch("/employees/{employee_id}/employment", response_model=Message)
def save_employment(employee_id: int, payload: EmploymentStep, principal: ManageAccess):
    """Step 3. Also creates the employee's leave balances once a joining date exists."""
    db = principal.db
    employee = _employee(principal, employee_id)
    data = payload.model_dump(exclude_unset=True)

    code = data.pop("employee_code", None)
    if code:
        clash = db.scalar(
            select(Employee.id).where(
                Employee.company_id == principal.tenant_id,
                Employee.employee_code == code.strip(),
                Employee.id != employee.id,
            )
        )
        if clash:
            raise Conflict(f"Employee code {code} is already in use")
        employee.employee_code = code.strip()

    if "status" in data:
        employee.status = data.pop("status")

    if data.get("manager_id") == employee.id:
        raise BadRequest("An employee cannot be their own manager")

    detail = hr_service.ensure_employment(db, employee, data.get("joining_date") or today())
    for field, value in data.items():
        setattr(detail, field, value)

    db.flush()
    leave_service.ensure_leave_balances(db, employee)
    db.commit()
    return Message(message="Employment details saved")


@router.put("/employees/{employee_id}/bank", response_model=BankOut)
def save_bank(employee_id: int, payload: BankStep, principal: SalaryAccess):
    """Step 5a. Behind salary permission — this is payment information."""
    employee = _employee(principal, employee_id)
    record = hr_service.upsert_bank(principal.db, employee, payload)
    notification_service.audit(
        principal.db, company_id=principal.tenant_id, user_id=principal.user_id,
        action="employee.bank_updated", entity_type="employee", entity_id=employee.id,
    )
    principal.db.commit()
    principal.db.refresh(record)
    return _bank_out(record, reveal=True)


def _bank_out(record: EmployeeBankDetail | None, reveal: bool) -> BankOut:
    if record is None:
        return BankOut(
            bank_name=None, account_holder_name=None, account_number=None,
            account_number_masked=None, ifsc=None, branch=None,
        )
    return BankOut(
        bank_name=record.bank_name,
        account_holder_name=record.account_holder_name,
        # Full number only for callers allowed to see it.
        account_number=record.account_number if reveal else None,
        account_number_masked=record.masked_account_number,
        ifsc=record.ifsc,
        branch=record.branch,
    )


@router.get("/employees/{employee_id}/bank", response_model=BankOut)
def get_bank(employee_id: int, principal: CurrentUser):
    """Masked by default; the full number needs salary:read."""
    employee = _employee(principal, employee_id)
    me = principal.employee
    is_self = me is not None and me.id == employee.id
    if not principal.has(P.SALARY_READ) and not is_self:
        raise NotFound("Employee not found")

    record = principal.db.scalar(
        select(EmployeeBankDetail).where(EmployeeBankDetail.employee_id == employee.id)
    )
    return _bank_out(record, reveal=principal.has(P.SALARY_READ))


@router.put("/employees/{employee_id}/statutory", response_model=StatutoryOut)
def save_statutory(employee_id: int, payload: StatutoryStep, principal: ManageAccess):
    """Step 5b."""
    employee = _employee(principal, employee_id)
    record = hr_service.upsert_statutory(principal.db, employee, payload)
    principal.db.commit()
    principal.db.refresh(record)
    return StatutoryOut.model_validate(record, from_attributes=True)


@router.get("/employees/{employee_id}/statutory", response_model=StatutoryOut)
def get_statutory(employee_id: int, principal: ReadAccess):
    employee = _employee(principal, employee_id)
    record = principal.db.scalar(
        select(EmployeeStatutoryDetail).where(
            EmployeeStatutoryDetail.employee_id == employee.id
        )
    )
    if record is None:
        return StatutoryOut()
    return StatutoryOut.model_validate(record, from_attributes=True)


@router.get("/employees/{employee_id}/review", response_model=EmployeeReview)
def review(employee_id: int, principal: ReadAccess):
    """Step 6 — the final screen, and the gate for completion."""
    return hr_service.build_review(principal.db, _employee(principal, employee_id))


@router.post("/employees/{employee_id}/complete", response_model=EmployeeReview)
def complete(
    employee_id: int,
    principal: ManageAccess,
    force: bool = Query(False, description="Override missing required documents"),
):
    """Marks a draft COMPLETE. Refuses while required documents are outstanding."""
    db = principal.db
    employee = _employee(principal, employee_id)

    if force and not principal.has(P.SETTINGS_MANAGE):
        raise BadRequest("Only an administrator can complete an employee with documents missing")

    hr_service.complete_employee(db, employee, force=force)
    notification_service.audit(
        db, company_id=principal.tenant_id, user_id=principal.user_id,
        action="employee.completed", entity_type="employee", entity_id=employee.id,
        changes={"forced": force},
    )
    notification_service.notify_employee(
        db, employee,
        event=NotificationEvent.EMPLOYEE_ADDED,
        title="Your profile is complete",
        message=f"Your employee record ({employee.employee_code}) has been finalised.",
        entity_type="employee", entity_id=employee.id,
    )
    db.commit()
    db.refresh(employee)
    return hr_service.build_review(db, employee)


# ---------------------------------------------------------------- document policy


@router.get("/document-policy", response_model=list[DocumentPolicyOut])
def read_policy(principal: CurrentUser):
    principal.require(P.EMPLOYEE_READ_ALL, P.DOCUMENT_READ_SELF)
    return hr_service.get_policy(principal.db, principal.tenant_id)


@router.put("/document-policy", response_model=list[DocumentPolicyOut])
def write_policy(payload: DocumentPolicyUpdate, principal: Perm(P.SETTINGS_MANAGE, P.ORG_MANAGE)):
    """Sets which document types this company requires."""
    db, tenant = principal.db, principal.tenant_id
    existing = {p.document_type: p for p in hr_service.get_policy(db, tenant)}

    for item in payload.policies:
        row = existing.get(item.document_type)
        if row is None:
            row = DocumentPolicy(company_id=tenant, document_type=item.document_type)
            db.add(row)
        row.is_required = item.is_required
        row.tracks_expiry = item.tracks_expiry
        row.display_order = item.display_order
        row.is_active = item.is_active

    notification_service.audit(
        db, company_id=tenant, user_id=principal.user_id,
        action="document_policy.update", entity_type="document_policy",
        changes={"required": [p.document_type.value for p in payload.policies if p.is_required]},
    )
    db.commit()
    return hr_service.get_policy(db, tenant)


# ---------------------------------------------------------------- verification


@router.get("/employees/{employee_id}/documents/checklist", response_model=DocumentChecklist)
def checklist(employee_id: int, principal: CurrentUser):
    """Policy vs. what's actually on file for this employee."""
    employee = _employee(principal, employee_id)
    me = principal.employee
    if not principal.has(P.DOCUMENT_READ_ALL, P.DOCUMENT_MANAGE):
        if me is None or me.id != employee.id:
            raise NotFound("Employee not found")
    return hr_service.build_checklist(principal.db, employee)


def _require_document(principal, document_id: int) -> EmployeeDocument:
    doc = principal.db.get(EmployeeDocument, document_id)
    if doc is None or doc.company_id != principal.tenant_id:
        raise NotFound("Document not found")
    return doc


@router.post("/documents/{document_id}/verify", response_model=DocumentOut)
def verify_document(document_id: int, payload: DocumentVerify, principal: DocAccess):
    from app.api.v1.documents import to_out

    doc = _require_document(principal, document_id)
    doc.status = DocumentStatus.VERIFIED
    doc.verified_by_user_id = principal.user_id
    doc.verified_at = utcnow()
    doc.rejection_reason = None
    if payload.expiry_date:
        doc.expiry_date = payload.expiry_date

    notification_service.notify_employee(
        principal.db, doc.employee,
        event=NotificationEvent.DOCUMENT_UPLOADED,
        title="Document verified",
        message=f"Your {doc.title} has been verified.",
        entity_type="document", entity_id=doc.id, action_url="/documents",
    )
    principal.db.commit()
    principal.db.refresh(doc)
    return to_out(doc)


@router.post("/documents/{document_id}/reject", response_model=DocumentOut)
def reject_document(document_id: int, payload: DocumentReject, principal: DocAccess):
    """Rejection always carries a reason — the employee needs to know what to fix."""
    from app.api.v1.documents import to_out

    doc = _require_document(principal, document_id)
    doc.status = DocumentStatus.REJECTED
    doc.verified_by_user_id = principal.user_id
    doc.verified_at = utcnow()
    doc.rejection_reason = payload.reason

    notification_service.notify_employee(
        principal.db, doc.employee,
        event=NotificationEvent.DOCUMENT_UPLOADED,
        title=f"{doc.title} was rejected",
        message=f"Reason: {payload.reason}. Please upload it again.",
        entity_type="document", entity_id=doc.id, action_url="/documents",
    )
    principal.db.commit()
    principal.db.refresh(doc)
    return to_out(doc)


@router.get("/documents", response_model=Page[DocumentOut])
def list_documents(
    pagination: Pagination,
    principal: Perm(P.DOCUMENT_READ_ALL, P.DOCUMENT_MANAGE),
    status_: DocumentStatus | None = Query(None, alias="status"),
    document_type: DocumentType | None = None,
    employee_id: int | None = None,
    department_id: int | None = None,
    expiring_before: date | None = None,
):
    """The HR document register, with the filters the dashboard needs."""
    from app.api.v1.documents import to_out
    from app.models.employee import EmployeeEmploymentDetail

    stmt = select(EmployeeDocument).where(EmployeeDocument.company_id == principal.tenant_id)
    if status_:
        stmt = stmt.where(EmployeeDocument.status == status_)
    if document_type:
        stmt = stmt.where(EmployeeDocument.document_type == document_type)
    if employee_id:
        stmt = stmt.where(EmployeeDocument.employee_id == employee_id)
    if expiring_before:
        stmt = stmt.where(
            EmployeeDocument.expiry_date.is_not(None),
            EmployeeDocument.expiry_date <= expiring_before,
        )
    if department_id:
        stmt = stmt.where(
            EmployeeDocument.employee_id.in_(
                select(EmployeeEmploymentDetail.employee_id).where(
                    EmployeeEmploymentDetail.department_id == department_id
                )
            )
        )

    stmt = stmt.order_by(EmployeeDocument.created_at.desc())
    rows, total = paginate(principal.db, stmt, pagination)
    return build_page([to_out(r) for r in rows], total, pagination)


@router.get("/documents/dashboard", response_model=DocumentDashboard)
def documents_dashboard(principal: Perm(P.DOCUMENT_READ_ALL, P.DOCUMENT_MANAGE)):
    kpis = hr_service.document_kpis(principal.db, principal.tenant_id)
    return DocumentDashboard(
        kpis=DocumentKpis(**kpis),
        employees_with_missing_required=hr_service.employees_missing_required(
            principal.db, principal.tenant_id
        ),
    )


# ---------------------------------------------------------------- HR overview


@router.get("/overview")
def hr_overview(principal: Perm(P.DASHBOARD_HR)):
    """Counts and lists for the HR landing page."""
    db, tenant = principal.db, principal.tenant_id
    from app.models.employee import EmployeeEmploymentDetail
    from app.models.enums import EmployeeStatus

    total = db.scalar(select(func.count(Employee.id)).where(Employee.company_id == tenant)) or 0
    active = (
        db.scalar(
            select(func.count(Employee.id)).where(
                Employee.company_id == tenant,
                Employee.status.in_(
                    [EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION, EmployeeStatus.NOTICE_PERIOD]
                ),
            )
        )
        or 0
    )
    drafts = (
        db.scalar(
            select(func.count(Employee.id)).where(
                Employee.company_id == tenant,
                Employee.profile_status == ProfileStatus.DRAFT,
            )
        )
        or 0
    )
    kpis = hr_service.document_kpis(db, tenant)

    upcoming = db.execute(
        select(Employee, EmployeeEmploymentDetail)
        .join(EmployeeEmploymentDetail, EmployeeEmploymentDetail.employee_id == Employee.id)
        .where(
            Employee.company_id == tenant,
            EmployeeEmploymentDetail.joining_date > today(),
        )
        .order_by(EmployeeEmploymentDetail.joining_date)
        .limit(10)
    ).all()

    recent = db.execute(
        select(Employee, EmployeeEmploymentDetail)
        .join(EmployeeEmploymentDetail, EmployeeEmploymentDetail.employee_id == Employee.id)
        .where(Employee.company_id == tenant)
        .order_by(Employee.created_at.desc())
        .limit(10)
    ).all()

    def mini(employee, detail):
        return {
            "id": employee.id,
            "employee_code": employee.employee_code,
            "full_name": employee.full_name,
            "designation": detail.designation.name if detail and detail.designation else None,
            "joining_date": str(detail.joining_date) if detail else None,
            "profile_status": employee.profile_status.value,
        }

    return {
        "counts": {
            "total_employees": total,
            "active": active,
            "draft_profiles": drafts,
            "pending_documents": kpis["pending"],
            "rejected_documents": kpis["rejected"],
        },
        "documents": kpis,
        "upcoming_joiners": [mini(e, d) for e, d in upcoming],
        "recent_employees": [mini(e, d) for e, d in recent],
    }
