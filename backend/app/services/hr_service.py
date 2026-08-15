"""HR employee-record services: code generation, document policy, review gating."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequest, Conflict, NotFound
from app.models.company import Company
from app.models.document import EmployeeDocument
from app.models.employee import (
    Employee,
    EmployeeEmploymentDetail,
    EmployeePersonalDetail,
)
from app.models.enums import DocumentStatus, DocumentType, ProfileStatus
from app.models.onboarding_records import (
    DocumentPolicy,
    EmployeeBankDetail,
    EmployeeStatutoryDetail,
)
from app.schemas.hr import (
    ChecklistRow,
    DocumentChecklist,
    EmployeeReview,
    ReviewItem,
    ReviewSection,
)

# Sensible starting policy for an Indian company. HR can change any of it.
DEFAULT_POLICY: list[tuple[DocumentType, bool, bool, int]] = [
    # (type, required, tracks expiry, order)
    (DocumentType.RESUME, True, False, 1),
    (DocumentType.PAN, True, False, 2),
    (DocumentType.AADHAAR, True, False, 3),
    (DocumentType.OFFER_LETTER, True, False, 4),
    (DocumentType.JOINING_LETTER, True, False, 5),
    (DocumentType.BANK_PROOF, True, False, 6),
    (DocumentType.EXPERIENCE_LETTER, False, False, 7),
    (DocumentType.EDUCATION, False, False, 8),
    (DocumentType.ADDRESS_PROOF, False, False, 9),
    (DocumentType.WORK_PERMIT, False, True, 10),
    (DocumentType.OTHER, False, False, 11),
]


# ---------------------------------------------------------------- employee code


def generate_employee_code(db: Session, company: Company) -> str:
    """Next code from the company's format, e.g. `EMP-{NUMBER}` -> `EMP-0007`.

    Skips numbers already taken by manually entered codes so the sequence can
    never produce a duplicate.
    """
    fmt = company.employee_id_format or "EMP-{NUMBER}"
    padding = company.employee_id_padding or 4

    taken = {
        code
        for code in db.scalars(
            select(Employee.employee_code).where(Employee.company_id == company.id)
        )
    }

    counter = max(company.employee_id_next or 1, 1)
    for _ in range(10_000):
        candidate = fmt.replace("{NUMBER}", str(counter).zfill(padding))
        if candidate not in taken:
            company.employee_id_next = counter + 1
            return candidate
        counter += 1
    raise BadRequest("Could not allocate an employee code — check the format in Settings")


def preview_employee_codes(company: Company, count: int = 3) -> list[str]:
    """What the next few codes would look like, for the settings screen."""
    fmt = company.employee_id_format or "EMP-{NUMBER}"
    padding = company.employee_id_padding or 4
    start = max(company.employee_id_next or 1, 1)
    return [fmt.replace("{NUMBER}", str(start + i).zfill(padding)) for i in range(count)]


# ---------------------------------------------------------------- document policy


def get_policy(db: Session, company_id: int) -> list[DocumentPolicy]:
    """The company's policy, seeded with sensible defaults on first read."""
    rows = list(
        db.scalars(
            select(DocumentPolicy)
            .where(DocumentPolicy.company_id == company_id)
            .order_by(DocumentPolicy.display_order)
        )
    )
    if rows:
        return rows

    for doc_type, required, expiry, order in DEFAULT_POLICY:
        db.add(
            DocumentPolicy(
                company_id=company_id,
                document_type=doc_type,
                is_required=required,
                tracks_expiry=expiry,
                display_order=order,
            )
        )
    db.commit()
    return list(
        db.scalars(
            select(DocumentPolicy)
            .where(DocumentPolicy.company_id == company_id)
            .order_by(DocumentPolicy.display_order)
        )
    )


def required_types(db: Session, company_id: int) -> list[DocumentType]:
    return [p.document_type for p in get_policy(db, company_id) if p.is_required and p.is_active]


# ---------------------------------------------------------------- checklist


def build_checklist(db: Session, employee: Employee) -> DocumentChecklist:
    """Every policy line for this employee, with whatever has been uploaded."""
    policy = [p for p in get_policy(db, employee.company_id) if p.is_active]

    documents = list(
        db.scalars(
            select(EmployeeDocument)
            .where(EmployeeDocument.employee_id == employee.id)
            .order_by(EmployeeDocument.created_at.desc())
        )
    )
    # Most recent upload per type wins.
    latest: dict[DocumentType, EmployeeDocument] = {}
    for doc in documents:
        latest.setdefault(doc.document_type, doc)

    rows: list[ChecklistRow] = []
    for entry in policy:
        doc = latest.get(entry.document_type)
        status = doc.status if doc else None
        # Surface expiry without waiting for a nightly job to flip the status.
        if doc and doc.expiry_date and doc.expiry_date < date.today():
            status = DocumentStatus.EXPIRED
        rows.append(
            ChecklistRow(
                document_type=entry.document_type,
                is_required=entry.is_required,
                document_id=doc.id if doc else None,
                file_name=doc.file_name if doc else None,
                status=status,
                expiry_date=doc.expiry_date if doc else None,
                uploaded_at=doc.created_at if doc else None,
                rejection_reason=doc.rejection_reason if doc else None,
                missing=doc is None,
            )
        )

    required = [r for r in rows if r.is_required]
    verified = [r for r in required if r.status == DocumentStatus.VERIFIED]
    return DocumentChecklist(
        employee_id=employee.id,
        required_total=len(required),
        required_verified=len(verified),
        complete=len(required) == len(verified),
        rows=rows,
    )


# ---------------------------------------------------------------- review / completion


def build_review(db: Session, employee: Employee) -> EmployeeReview:
    """The wizard's final screen: what's done, what's blocking completion."""
    personal = employee.personal
    employment = employee.employment
    bank = db.scalar(
        select(EmployeeBankDetail).where(EmployeeBankDetail.employee_id == employee.id)
    )
    statutory = db.scalar(
        select(EmployeeStatutoryDetail).where(EmployeeStatutoryDetail.employee_id == employee.id)
    )
    checklist = build_checklist(db, employee)

    def item(label, value, detail=None):
        return ReviewItem(label=label, ok=bool(value), detail=detail or (str(value) if value else None))

    personal_items = [
        item("Name", employee.full_name),
        item("Date of birth", personal.date_of_birth if personal else None),
        item("Gender", personal.gender.value if personal and personal.gender else None),
    ]
    contact_items = [
        item("Personal email", personal.personal_email if personal else None),
        item("Phone", personal.phone if personal else None),
        item("Emergency contact", personal.emergency_contact_name if personal else None),
    ]
    employment_items = [
        item("Employee ID", employee.employee_code),
        item("Joining date", employment.joining_date if employment else None),
        item("Department", employment.department.name if employment and employment.department else None),
        item("Designation", employment.designation.name if employment and employment.designation else None),
        item("Location", employment.location.name if employment and employment.location else None),
        item("Manager", employment.manager.full_name if employment and employment.manager else None),
    ]
    document_items = [
        ReviewItem(
            label=row.document_type.value.replace("_", " ").title(),
            ok=row.status == DocumentStatus.VERIFIED,
            detail=(
                "Missing"
                if row.missing
                else (row.status.value.title() if row.status else "Uploaded")
            )
            + ("" if row.is_required else " (optional)"),
        )
        for row in checklist.rows
        if row.is_required or not row.missing
    ]
    bank_items = [
        item("Account number", bank.account_number if bank else None, bank.masked_account_number if bank else None),
        item("IFSC", bank.ifsc if bank else None),
    ]
    statutory_items = [
        item("PAN", statutory.pan if statutory else None),
        ReviewItem(
            label="Provident Fund",
            ok=not (statutory and statutory.pf_eligible) or bool(statutory.uan),
            detail="Not eligible" if not (statutory and statutory.pf_eligible)
            else (statutory.uan or "Eligible but UAN missing"),
        ),
    ]

    sections = [
        ReviewSection(name="Personal", complete=all(i.ok for i in personal_items), items=personal_items),
        ReviewSection(name="Contact", complete=all(i.ok for i in contact_items), items=contact_items),
        ReviewSection(
            name="Employment",
            complete=all(i.ok for i in employment_items[:2]),
            items=employment_items,
        ),
        ReviewSection(name="Documents", complete=checklist.complete, items=document_items),
        ReviewSection(name="Bank", complete=all(i.ok for i in bank_items), items=bank_items),
        ReviewSection(name="Statutory", complete=all(i.ok for i in statutory_items), items=statutory_items),
    ]

    # Only these actually stop completion — the rest is guidance.
    blocking: list[str] = []
    if not employment or not employment.joining_date:
        blocking.append("Joining date is required")
    for row in checklist.rows:
        if not row.is_required:
            continue
        if row.missing:
            blocking.append(f"{row.document_type.value.replace('_', ' ').title()} is missing")
        elif row.status != DocumentStatus.VERIFIED:
            label = row.document_type.value.replace("_", " ").title()
            blocking.append(f"{label} is {(row.status or DocumentStatus.PENDING).value.lower()}")

    return EmployeeReview(
        employee_id=employee.id,
        employee_code=employee.employee_code,
        full_name=employee.full_name,
        profile_status=employee.profile_status,
        can_complete=not blocking,
        blocking=blocking,
        sections=sections,
    )


def complete_employee(db: Session, employee: Employee, force: bool = False) -> Employee:
    """Moves a draft to COMPLETE, refusing while required documents are outstanding.

    `force` lets an admin override — the audit log records who did it.
    """
    review = build_review(db, employee)
    if not review.can_complete and not force:
        raise BadRequest(
            "This employee cannot be completed yet: " + "; ".join(review.blocking)
        )
    employee.profile_status = ProfileStatus.COMPLETE
    db.flush()
    return employee


# ---------------------------------------------------------------- helpers


def upsert_bank(db: Session, employee: Employee, payload) -> EmployeeBankDetail:
    record = db.scalar(
        select(EmployeeBankDetail).where(EmployeeBankDetail.employee_id == employee.id)
    )
    if record is None:
        record = EmployeeBankDetail(employee_id=employee.id, company_id=employee.company_id)
        db.add(record)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    db.flush()
    return record


def upsert_statutory(db: Session, employee: Employee, payload) -> EmployeeStatutoryDetail:
    record = db.scalar(
        select(EmployeeStatutoryDetail).where(
            EmployeeStatutoryDetail.employee_id == employee.id
        )
    )
    if record is None:
        record = EmployeeStatutoryDetail(employee_id=employee.id, company_id=employee.company_id)
        db.add(record)

    data = payload.model_dump(exclude_unset=True)
    # Clearing eligibility should clear the numbers with it, so stale IDs don't
    # linger on an employee who no longer contributes.
    if data.get("pf_eligible") is False:
        data["uan"] = None
        data["pf_number"] = None
    if data.get("esi_eligible") is False:
        data["esi_number"] = None

    for field, value in data.items():
        setattr(record, field, value)
    db.flush()
    return record


def ensure_personal(db: Session, employee: Employee) -> EmployeePersonalDetail:
    if employee.personal is None:
        detail = EmployeePersonalDetail(
            employee_id=employee.id, company_id=employee.company_id
        )
        db.add(detail)
        db.flush()
        db.refresh(employee)
    return employee.personal


def ensure_employment(db: Session, employee: Employee, joining_date: date) -> EmployeeEmploymentDetail:
    if employee.employment is None:
        detail = EmployeeEmploymentDetail(
            employee_id=employee.id,
            company_id=employee.company_id,
            joining_date=joining_date,
        )
        db.add(detail)
        db.flush()
        db.refresh(employee)
    return employee.employment


def document_kpis(db: Session, company_id: int) -> dict:
    counts = dict(
        db.execute(
            select(EmployeeDocument.status, func.count(EmployeeDocument.id))
            .where(EmployeeDocument.company_id == company_id)
            .group_by(EmployeeDocument.status)
        ).all()
    )
    total = sum(counts.values())
    return {
        "total": total,
        "verified": counts.get(DocumentStatus.VERIFIED, 0),
        "pending": counts.get(DocumentStatus.PENDING, 0),
        "rejected": counts.get(DocumentStatus.REJECTED, 0),
        "expired": counts.get(DocumentStatus.EXPIRED, 0),
    }


def employees_missing_required(db: Session, company_id: int) -> int:
    """How many employees still owe a required document."""
    needed = set(required_types(db, company_id))
    if not needed:
        return 0

    employees = list(db.scalars(select(Employee).where(Employee.company_id == company_id)))
    count = 0
    for employee in employees:
        verified = {
            doc_type
            for doc_type in db.scalars(
                select(EmployeeDocument.document_type).where(
                    EmployeeDocument.employee_id == employee.id,
                    EmployeeDocument.status == DocumentStatus.VERIFIED,
                )
            )
        }
        if needed - verified:
            count += 1
    return count


def require_employee(db: Session, company_id: int, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None or employee.company_id != company_id:
        raise NotFound("Employee not found")
    return employee
