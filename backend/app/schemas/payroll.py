from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import CalculationType, ComponentType, PayrollStatus
from app.schemas.common import ORMModel


class SalaryComponentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=30)
    component_type: ComponentType
    calculation_type: CalculationType = CalculationType.FIXED
    default_value: float = Field(default=0, ge=0)
    is_taxable: bool = True
    prorate_on_lop: bool = True
    display_order: int = 0


class SalaryComponentUpdate(BaseModel):
    name: str | None = None
    calculation_type: CalculationType | None = None
    default_value: float | None = Field(default=None, ge=0)
    is_taxable: bool | None = None
    prorate_on_lop: bool | None = None
    display_order: int | None = None
    is_active: bool | None = None


class SalaryComponentOut(ORMModel):
    id: int
    name: str
    code: str
    component_type: ComponentType
    calculation_type: CalculationType
    default_value: float
    is_taxable: bool
    prorate_on_lop: bool
    display_order: int
    is_active: bool


class StructureComponentIn(BaseModel):
    component_id: int
    value: float = Field(ge=0)


class SalaryStructureCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    components: list[StructureComponentIn] = []


class StructureComponentOut(BaseModel):
    component_id: int
    code: str
    name: str
    component_type: ComponentType
    calculation_type: CalculationType
    value: float


class SalaryStructureOut(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    components: list[StructureComponentOut] = []


class EmployeeSalaryComponentIn(BaseModel):
    component_id: int
    monthly_amount: float = Field(ge=0)


class EmployeeSalaryCreate(BaseModel):
    structure_id: int | None = None
    ctc: float = Field(gt=0)
    effective_from: date
    payment_mode: str | None = None
    bank_account_number: str | None = None
    bank_ifsc: str | None = None
    # Leave empty to derive amounts from the structure's calculation rules.
    components: list[EmployeeSalaryComponentIn] = []


class SalaryComponentAmountOut(BaseModel):
    component_id: int
    code: str
    name: str
    component_type: ComponentType
    monthly_amount: float


class EmployeeSalaryOut(BaseModel):
    id: int
    employee_id: int
    employee_name: str | None = None
    structure_id: int | None
    ctc: float
    gross_monthly: float
    deductions_monthly: float
    net_monthly: float
    effective_from: date
    effective_to: date | None
    is_active: bool
    payment_mode: str | None
    bank_account_number: str | None
    bank_ifsc: str | None
    components: list[SalaryComponentAmountOut] = []


class PayrollRunCreate(BaseModel):
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)
    employee_ids: list[int] | None = None
    notes: str | None = None


class PayrollLineOut(BaseModel):
    code: str
    name: str
    amount: float


class PayrollItemOut(BaseModel):
    id: int
    employee_id: int
    employee_code: str | None = None
    employee_name: str | None = None
    working_days: float
    paid_days: float
    lop_days: float
    gross_earnings: float
    total_deductions: float
    net_pay: float
    earnings_breakdown: list[PayrollLineOut] = []
    deductions_breakdown: list[PayrollLineOut] = []
    lop_breakdown: dict = {}


class PayrollRunOut(ORMModel):
    id: int
    month: int
    year: int
    status: PayrollStatus
    employee_count: int
    total_gross: float
    total_deductions: float
    total_net: float
    processed_at: datetime | None
    approved_at: datetime | None
    notes: str | None
    created_at: datetime


class PayrollRunDetail(PayrollRunOut):
    items: list[PayrollItemOut] = []


class PayslipOut(BaseModel):
    id: int
    payslip_number: str
    payroll_run_id: int
    employee_id: int
    employee_name: str | None = None
    employee_code: str | None = None
    month: int
    year: int
    net_pay: float
    generated_at: datetime | None
    snapshot: dict = {}
