from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ComplianceUpdate(BaseModel):
    pf_enabled: bool | None = None
    pf_number: str | None = Field(default=None, max_length=60)
    pf_employee_rate: float | None = Field(default=None, ge=0, le=100)
    pf_employer_rate: float | None = Field(default=None, ge=0, le=100)
    pf_wage_ceiling: float | None = Field(default=None, ge=0)

    esi_enabled: bool | None = None
    esi_number: str | None = Field(default=None, max_length=60)
    esi_employee_rate: float | None = Field(default=None, ge=0, le=100)
    esi_employer_rate: float | None = Field(default=None, ge=0, le=100)
    esi_wage_ceiling: float | None = Field(default=None, ge=0)

    pt_enabled: bool | None = None
    pt_state: str | None = Field(default=None, max_length=80)
    pt_monthly_amount: float | None = Field(default=None, ge=0)

    tds_enabled: bool | None = None
    tan: str | None = Field(default=None, max_length=20)

    pan: str | None = Field(default=None, max_length=20)
    gstin: str | None = Field(default=None, max_length=20)
    cin: str | None = Field(default=None, max_length=30)
    labour_licence_number: str | None = Field(default=None, max_length=60)

    max_weekly_hours: float | None = Field(default=None, ge=0, le=168)
    min_break_minutes: int | None = Field(default=None, ge=0, le=480)


class ComplianceOut(ORMModel):
    id: int
    company_id: int

    pf_enabled: bool
    pf_number: str | None
    pf_employee_rate: float
    pf_employer_rate: float
    pf_wage_ceiling: float

    esi_enabled: bool
    esi_number: str | None
    esi_employee_rate: float
    esi_employer_rate: float
    esi_wage_ceiling: float

    pt_enabled: bool
    pt_state: str | None
    pt_monthly_amount: float

    tds_enabled: bool
    tan: str | None

    pan: str | None
    gstin: str | None
    cin: str | None
    labour_licence_number: str | None

    max_weekly_hours: float
    min_break_minutes: int


class ComplianceCheck(BaseModel):
    """One readiness item shown on the compliance dashboard."""

    label: str
    ok: bool
    detail: str


class ComplianceStatus(BaseModel):
    ready: bool
    checks: list[ComplianceCheck]
