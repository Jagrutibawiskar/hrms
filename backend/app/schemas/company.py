from datetime import date as date_type
from datetime import datetime, time

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.enums import CompanySize, HolidayType, OnboardingStep
from app.schemas.common import ORMModel


class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    industry: str = Field(min_length=2, max_length=100)
    company_size: CompanySize
    company_type: str | None = Field(default=None, max_length=100)

    email: EmailStr
    phone: str = Field(min_length=6, max_length=30)
    website: str | None = Field(default=None, max_length=255)

    country: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=3, max_length=500)
    postal_code: str = Field(min_length=3, max_length=20)

    timezone: str = "Asia/Kolkata"
    currency: str = "INR"
    fiscal_year_start_month: int = Field(default=4, ge=1, le=12)


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    industry: str | None = None
    company_size: CompanySize | None = None
    company_type: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    website: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    address: str | None = None
    postal_code: str | None = None
    timezone: str | None = None
    currency: str | None = None
    fiscal_year_start_month: int | None = Field(default=None, ge=1, le=12)
    geofence_enabled: bool | None = None
    max_regularizations_per_month: int | None = Field(default=None, ge=0, le=31)
    # Must contain {NUMBER}; that's where the sequence is substituted.
    employee_id_format: str | None = Field(default=None, min_length=1, max_length=40)
    employee_id_padding: int | None = Field(default=None, ge=1, le=10)


class CompanyOut(ORMModel):
    id: int
    name: str
    industry: str
    company_size: str
    company_type: str | None
    email: str
    phone: str
    website: str | None
    country: str
    state: str
    city: str
    address: str
    postal_code: str
    timezone: str
    currency: str
    fiscal_year_start_month: int
    onboarding_step: OnboardingStep
    is_onboarded: bool
    is_active: bool
    logo_path: str | None = None
    logo_url: str | None = None
    geofence_enabled: bool = False
    max_regularizations_per_month: int = 3
    employee_id_format: str = "EMP-{NUMBER}"
    employee_id_padding: int = 4
    created_at: datetime


# ---------------------------------------------------------------- organization


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=20)
    description: str | None = None
    head_employee_id: int | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    code: str | None = None
    description: str | None = None
    head_employee_id: int | None = None
    is_active: bool | None = None


class DepartmentOut(ORMModel):
    id: int
    name: str
    code: str | None
    description: str | None
    head_employee_id: int | None
    is_active: bool
    employee_count: int = 0


class DesignationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    department_id: int | None = None
    level: int | None = None
    description: str | None = None


class DesignationUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    department_id: int | None = None
    level: int | None = None
    description: str | None = None
    is_active: bool | None = None


class DesignationOut(ORMModel):
    id: int
    name: str
    department_id: int | None
    level: int | None
    description: str | None
    is_active: bool


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    timezone: str | None = None
    is_headquarters: bool = False
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    geofence_radius_m: int = Field(default=100, ge=10, le=10000)


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    timezone: str | None = None
    is_headquarters: bool | None = None
    is_active: bool | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    geofence_radius_m: int | None = Field(default=None, ge=10, le=10000)


class LocationOut(ORMModel):
    id: int
    name: str
    address: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    timezone: str | None
    is_headquarters: bool
    is_active: bool
    latitude: float | None = None
    longitude: float | None = None
    geofence_radius_m: int = 100


# ---------------------------------------------------------------- work policy


class WorkPolicyIn(BaseModel):
    name: str = "Default Work Policy"
    working_days: list[int] = Field(default=[1, 2, 3, 4, 5], min_length=1, max_length=7)
    start_time: time
    end_time: time
    break_start: time | None = None
    break_end: time | None = None
    full_day_hours: float = Field(default=8, gt=0, le=24)
    half_day_hours: float = Field(default=4, gt=0, le=24)
    late_grace_minutes: int = Field(default=15, ge=0, le=240)

    @model_validator(mode="after")
    def _check(self):
        if not all(1 <= d <= 7 for d in self.working_days):
            raise ValueError("working_days must be ISO weekday numbers (Monday=1 .. Sunday=7)")
        if len(set(self.working_days)) != len(self.working_days):
            raise ValueError("working_days must not contain duplicates")
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        if (self.break_start is None) != (self.break_end is None):
            raise ValueError("break_start and break_end must be provided together")
        if self.break_start and self.break_end and self.break_start >= self.break_end:
            raise ValueError("break_start must be before break_end")
        if self.half_day_hours >= self.full_day_hours:
            raise ValueError("half_day_hours must be less than full_day_hours")
        return self


class WorkPolicyOut(ORMModel):
    id: int
    name: str
    working_days: list[int]
    weekly_off_days: list[int]
    start_time: time
    end_time: time
    break_start: time | None
    break_end: time | None
    full_day_hours: float
    half_day_hours: float
    late_grace_minutes: int
    is_default: bool
    is_active: bool


# ---------------------------------------------------------------- leave types


class LeaveTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=20)
    annual_quota: float = Field(default=0, ge=0, le=365)
    is_paid: bool = True
    requires_approval: bool = True
    allow_half_day: bool = True
    carry_forward: bool = False
    max_carry_forward: float = Field(default=0, ge=0)
    requires_attachment: bool = False


class LeaveTypeUpdate(BaseModel):
    name: str | None = None
    annual_quota: float | None = Field(default=None, ge=0, le=365)
    is_paid: bool | None = None
    requires_approval: bool | None = None
    allow_half_day: bool | None = None
    carry_forward: bool | None = None
    max_carry_forward: float | None = Field(default=None, ge=0)
    requires_attachment: bool | None = None
    is_active: bool | None = None


class LeaveTypeOut(ORMModel):
    id: int
    name: str
    code: str
    annual_quota: float
    is_paid: bool
    requires_approval: bool
    allow_half_day: bool
    carry_forward: bool
    max_carry_forward: float
    requires_attachment: bool
    is_active: bool


# ---------------------------------------------------------------- holidays


class HolidayCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    date: date_type
    holiday_type: HolidayType = HolidayType.PUBLIC
    location_id: int | None = None
    description: str | None = None


class HolidayUpdate(BaseModel):
    name: str | None = None
    date: date_type | None = None
    holiday_type: HolidayType | None = None
    location_id: int | None = None
    description: str | None = None


class HolidayOut(ORMModel):
    id: int
    name: str
    date: date_type
    holiday_type: HolidayType
    location_id: int | None
    description: str | None
