from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import (
    EmployeeStatus,
    EmploymentType,
    Gender,
    MaritalStatus,
    ProfileStatus,
    RoleName,
    WorkMode,
)
from app.schemas.common import ORMModel


class PersonalDetailsIn(BaseModel):
    date_of_birth: date | None = None
    gender: Gender | None = None
    marital_status: MaritalStatus | None = None
    blood_group: str | None = Field(default=None, max_length=10)
    personal_email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_relation: str | None = None
    emergency_contact_phone: str | None = None


class PersonalDetailsOut(ORMModel, PersonalDetailsIn):
    pass


class EmploymentDetailsIn(BaseModel):
    department_id: int | None = None
    designation_id: int | None = None
    location_id: int | None = None
    manager_id: int | None = None
    work_policy_id: int | None = None
    joining_date: date
    confirmation_date: date | None = None
    probation_months: int | None = Field(default=None, ge=0, le=36)
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    work_mode: WorkMode = WorkMode.OFFICE
    is_manager: bool = False


class EmploymentDetailsOut(ORMModel):
    department_id: int | None
    department_name: str | None = None
    designation_id: int | None
    designation_name: str | None = None
    location_id: int | None
    location_name: str | None = None
    manager_id: int | None
    manager_name: str | None = None
    work_policy_id: int | None
    joining_date: date
    confirmation_date: date | None
    probation_months: int | None
    employment_type: EmploymentType
    work_mode: WorkMode = WorkMode.OFFICE
    is_manager: bool
    exit_date: date | None
    exit_reason: str | None


class EmployeeCreate(BaseModel):
    employee_code: str | None = Field(default=None, max_length=40)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    work_email: EmailStr

    employment: EmploymentDetailsIn
    personal: PersonalDetailsIn | None = None

    status: EmployeeStatus = EmployeeStatus.ACTIVE
    # Creates a login for the employee. Omit the password to auto-generate one.
    create_login: bool = True
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: RoleName = RoleName.EMPLOYEE


class EmployeeUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    work_email: EmailStr | None = None
    status: EmployeeStatus | None = None
    employment: EmploymentDetailsIn | None = None
    personal: PersonalDetailsIn | None = None


class EmployeeListItem(BaseModel):
    id: int
    employee_code: str
    full_name: str
    work_email: str
    department_name: str | None = None
    designation_name: str | None = None
    manager_name: str | None = None
    location_name: str | None = None
    joining_date: date | None = None
    employment_type: str | None = None
    status: EmployeeStatus


class EmployeeOut(BaseModel):
    id: int
    company_id: int
    user_id: int | None
    employee_code: str
    first_name: str
    last_name: str | None
    full_name: str
    work_email: str
    profile_photo_path: str | None
    status: EmployeeStatus
    profile_status: ProfileStatus = ProfileStatus.COMPLETE
    roles: list[str] = []
    personal: PersonalDetailsOut | None = None
    employment: EmploymentDetailsOut | None = None
    created_at: datetime


class EmployeeDeactivate(BaseModel):
    exit_date: date | None = None
    exit_reason: str | None = None
    status: EmployeeStatus = EmployeeStatus.INACTIVE


class EmployeeImportRow(BaseModel):
    """One CSV row. Column names map 1:1 to these field names."""

    employee_code: str | None = None
    first_name: str
    last_name: str | None = None
    work_email: EmailStr
    department: str | None = None
    designation: str | None = None
    location: str | None = None
    manager_email: str | None = None
    joining_date: date
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    phone: str | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None


class ImportError_(BaseModel):
    row: int
    error: str


class ImportResult(BaseModel):
    created: int
    failed: int
    errors: list[ImportError_] = []
    created_employee_ids: list[int] = []


class AdminProfileIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str = Field(min_length=6, max_length=30)
    designation_id: int | None = None
    designation_name: str | None = None
    department_id: int | None = None
    location_id: int | None = None
    joining_date: date | None = None
