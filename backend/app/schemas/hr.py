"""Schemas for the HR employee wizard, documents and company document policy."""

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import (
    DocumentStatus,
    DocumentType,
    EmployeeStatus,
    EmploymentType,
    Gender,
    MaritalStatus,
    ProfileStatus,
    WorkMode,
)
from app.schemas.common import ORMModel

# ---------------------------------------------------------------- wizard steps


class PersonalStep(BaseModel):
    """Step 1. Only name and DOB/gender are treated as required by the UI."""

    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    gender: Gender | None = None
    blood_group: str | None = Field(default=None, max_length=10)
    nationality: str | None = Field(default=None, max_length=80)
    marital_status: MaritalStatus | None = None


class ContactStep(BaseModel):
    """Step 2."""

    personal_email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    alternate_phone: str | None = Field(default=None, max_length=30)
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_relation: str | None = None
    emergency_contact_phone: str | None = None


class EmploymentStep(BaseModel):
    """Step 3."""

    employee_code: str | None = Field(default=None, max_length=40)
    joining_date: date
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    work_mode: WorkMode = WorkMode.OFFICE
    department_id: int | None = None
    designation_id: int | None = None
    location_id: int | None = None
    manager_id: int | None = None
    work_policy_id: int | None = None
    probation_months: int | None = Field(default=None, ge=0, le=36)
    confirmation_date: date | None = None
    is_manager: bool = False
    status: EmployeeStatus = EmployeeStatus.ACTIVE


class BankStep(BaseModel):
    """Step 5a."""

    bank_name: str | None = Field(default=None, max_length=120)
    account_holder_name: str | None = Field(default=None, max_length=150)
    account_number: str | None = Field(default=None, max_length=40)
    ifsc: str | None = Field(default=None, max_length=20)
    branch: str | None = Field(default=None, max_length=150)


class BankOut(BaseModel):
    bank_name: str | None
    account_holder_name: str | None
    # Masked unless the caller holds salary:read — see the router.
    account_number: str | None
    account_number_masked: str | None
    ifsc: str | None
    branch: str | None


class StatutoryStep(BaseModel):
    """Step 5b. Nothing is forced — eligibility flags decide what's collected."""

    pan: str | None = Field(default=None, max_length=20)
    pf_eligible: bool = False
    uan: str | None = Field(default=None, max_length=30)
    pf_number: str | None = Field(default=None, max_length=40)
    esi_eligible: bool = False
    esi_number: str | None = Field(default=None, max_length=40)
    professional_tax_state: str | None = Field(default=None, max_length=80)


class StatutoryOut(StatutoryStep):
    pass


class DraftEmployeeCreate(BaseModel):
    """Starts the wizard. Everything else arrives step by step."""

    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    work_email: EmailStr
    employee_code: str | None = Field(default=None, max_length=40)
    joining_date: date | None = None


# ---------------------------------------------------------------- review


class ReviewItem(BaseModel):
    label: str
    ok: bool
    detail: str | None = None


class ReviewSection(BaseModel):
    name: str
    complete: bool
    items: list[ReviewItem]


class EmployeeReview(BaseModel):
    """Drives the wizard's final screen and gates `complete`."""

    employee_id: int
    employee_code: str
    full_name: str
    profile_status: ProfileStatus
    can_complete: bool
    blocking: list[str]
    sections: list[ReviewSection]


# ---------------------------------------------------------------- documents


class DocumentPolicyItem(BaseModel):
    document_type: DocumentType
    is_required: bool = False
    tracks_expiry: bool = False
    display_order: int = 0
    is_active: bool = True


class DocumentPolicyOut(ORMModel):
    id: int
    document_type: DocumentType
    is_required: bool
    tracks_expiry: bool
    display_order: int
    is_active: bool


class DocumentPolicyUpdate(BaseModel):
    policies: list[DocumentPolicyItem]


class DocumentVerify(BaseModel):
    expiry_date: date | None = None
    note: str | None = Field(default=None, max_length=500)


class DocumentReject(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ChecklistRow(BaseModel):
    """One line of an employee's document checklist."""

    document_type: DocumentType
    is_required: bool
    document_id: int | None = None
    file_name: str | None = None
    status: DocumentStatus | None = None
    expiry_date: date | None = None
    uploaded_at: datetime | None = None
    rejection_reason: str | None = None
    # Nothing uploaded at all.
    missing: bool = True


class DocumentChecklist(BaseModel):
    employee_id: int
    required_total: int
    required_verified: int
    complete: bool
    rows: list[ChecklistRow]


class DocumentKpis(BaseModel):
    total: int
    verified: int
    pending: int
    rejected: int
    expired: int


class DocumentDashboard(BaseModel):
    kpis: DocumentKpis
    employees_with_missing_required: int
