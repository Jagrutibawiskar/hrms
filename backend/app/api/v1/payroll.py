from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.deps import CurrentUser, Perm
from app.core.exceptions import BadRequest, Forbidden, NotFound
from app.core.pagination import Page, Pagination, build_page, paginate
from app.core.rbac import P
from app.models.enums import PayrollStatus
from app.models.payroll import (
    EmployeeSalary,
    PayrollItem,
    PayrollRun,
    Payslip,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureComponent,
)
from app.schemas.common import Message
from app.schemas.payroll import (
    EmployeeSalaryCreate,
    EmployeeSalaryOut,
    PayrollItemOut,
    PayrollLineOut,
    PayrollRunCreate,
    PayrollRunDetail,
    PayrollRunOut,
    PayslipOut,
    SalaryComponentAmountOut,
    SalaryComponentCreate,
    SalaryComponentOut,
    SalaryComponentUpdate,
    SalaryStructureCreate,
    SalaryStructureOut,
    StructureComponentOut,
)
from app.services import employee_service, notification_service, payroll_service

router = APIRouter(prefix="/payroll", tags=["Payroll"])

SalaryRead = Perm(P.SALARY_READ)
SalaryManage = Perm(P.SALARY_MANAGE)
ProcessAccess = Perm(P.PAYROLL_PROCESS)
ApproveAccess = Perm(P.PAYROLL_APPROVE)
PayrollRead = Perm(P.PAYROLL_READ_ALL)


def structure_out(structure: SalaryStructure) -> SalaryStructureOut:
    return SalaryStructureOut(
        id=structure.id,
        name=structure.name,
        description=structure.description,
        is_active=structure.is_active,
        components=[
            StructureComponentOut(
                component_id=row.component_id,
                code=row.component.code,
                name=row.component.name,
                component_type=row.component.component_type,
                calculation_type=row.component.calculation_type,
                value=float(row.value),
            )
            for row in sorted(structure.components, key=lambda c: c.component.display_order)
        ],
    )


def salary_out(salary: EmployeeSalary) -> EmployeeSalaryOut:
    return EmployeeSalaryOut(
        id=salary.id,
        employee_id=salary.employee_id,
        employee_name=salary.employee.full_name if salary.employee else None,
        structure_id=salary.structure_id,
        ctc=float(salary.ctc),
        gross_monthly=float(salary.gross_monthly),
        deductions_monthly=float(salary.deductions_monthly),
        net_monthly=float(salary.net_monthly),
        effective_from=salary.effective_from,
        effective_to=salary.effective_to,
        is_active=salary.is_active,
        payment_mode=salary.payment_mode,
        bank_account_number=salary.bank_account_number,
        bank_ifsc=salary.bank_ifsc,
        components=[
            SalaryComponentAmountOut(
                component_id=row.component_id,
                code=row.component.code,
                name=row.component.name,
                component_type=row.component.component_type,
                monthly_amount=float(row.monthly_amount),
            )
            for row in sorted(salary.components, key=lambda c: c.component.display_order)
        ],
    )


def item_out(item: PayrollItem) -> PayrollItemOut:
    return PayrollItemOut(
        id=item.id,
        employee_id=item.employee_id,
        employee_code=item.employee.employee_code if item.employee else None,
        employee_name=item.employee.full_name if item.employee else None,
        working_days=float(item.working_days),
        paid_days=float(item.paid_days),
        lop_days=float(item.lop_days),
        gross_earnings=float(item.gross_earnings),
        total_deductions=float(item.total_deductions),
        net_pay=float(item.net_pay),
        earnings_breakdown=[PayrollLineOut(**line) for line in item.earnings_breakdown or []],
        deductions_breakdown=[PayrollLineOut(**line) for line in item.deductions_breakdown or []],
        lop_breakdown=item.lop_breakdown or {},
    )


def payslip_out(payslip: Payslip) -> PayslipOut:
    return PayslipOut(
        id=payslip.id,
        payslip_number=payslip.payslip_number,
        payroll_run_id=payslip.payroll_run_id,
        employee_id=payslip.employee_id,
        employee_name=payslip.employee.full_name if payslip.employee else None,
        employee_code=payslip.employee.employee_code if payslip.employee else None,
        month=payslip.month,
        year=payslip.year,
        net_pay=float(payslip.net_pay),
        generated_at=payslip.generated_at,
        snapshot=payslip.snapshot or {},
    )


# --------------------------------------------------------------- components


@router.get("/components", response_model=list[SalaryComponentOut])
def list_components(principal: SalaryRead):
    return list(
        principal.db.scalars(
            select(SalaryComponent)
            .where(SalaryComponent.company_id == principal.tenant_id)
            .order_by(SalaryComponent.display_order, SalaryComponent.id)
        )
    )


@router.post("/components", response_model=SalaryComponentOut, status_code=status.HTTP_201_CREATED)
def create_component(payload: SalaryComponentCreate, principal: SalaryManage):
    data = payload.model_dump()
    data["code"] = data["code"].strip().upper()
    if principal.db.scalar(
        select(SalaryComponent).where(
            SalaryComponent.company_id == principal.tenant_id,
            SalaryComponent.code == data["code"],
        )
    ):
        raise BadRequest(f"Component code '{data['code']}' already exists")

    component = SalaryComponent(company_id=principal.tenant_id, **data)
    principal.db.add(component)
    principal.db.commit()
    principal.db.refresh(component)
    return component


@router.patch("/components/{component_id}", response_model=SalaryComponentOut)
def update_component(
    component_id: int, payload: SalaryComponentUpdate, principal: SalaryManage
):
    component = principal.db.get(SalaryComponent, component_id)
    if component is None or component.company_id != principal.tenant_id:
        raise NotFound("Salary component not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(component, field, value)
    principal.db.commit()
    principal.db.refresh(component)
    return component


# --------------------------------------------------------------- structures


@router.get("/structures", response_model=list[SalaryStructureOut])
def list_structures(principal: SalaryRead):
    rows = principal.db.scalars(
        select(SalaryStructure)
        .where(SalaryStructure.company_id == principal.tenant_id)
        .order_by(SalaryStructure.id)
    )
    return [structure_out(s) for s in rows]


@router.post("/structures", response_model=SalaryStructureOut, status_code=status.HTTP_201_CREATED)
def create_structure(payload: SalaryStructureCreate, principal: SalaryManage):
    db = principal.db
    if db.scalar(
        select(SalaryStructure).where(
            SalaryStructure.company_id == principal.tenant_id,
            SalaryStructure.name == payload.name.strip(),
        )
    ):
        raise BadRequest(f"A structure named '{payload.name}' already exists")

    structure = SalaryStructure(
        company_id=principal.tenant_id, name=payload.name.strip(), description=payload.description
    )
    db.add(structure)
    db.flush()

    for item in payload.components:
        component = db.get(SalaryComponent, item.component_id)
        if component is None or component.company_id != principal.tenant_id:
            raise BadRequest(f"Salary component {item.component_id} not found")
        db.add(
            SalaryStructureComponent(
                structure_id=structure.id, component_id=component.id, value=item.value
            )
        )
    db.commit()
    db.refresh(structure)
    return structure_out(structure)


@router.get("/structures/{structure_id}/preview", response_model=list[SalaryComponentAmountOut])
def preview_structure(
    structure_id: int, ctc: float, principal: SalaryRead
):
    """Shows the monthly breakup a given CTC would produce under this structure."""
    structure = principal.db.get(SalaryStructure, structure_id)
    if structure is None or structure.company_id != principal.tenant_id:
        raise NotFound("Salary structure not found")
    if ctc <= 0:
        raise BadRequest("ctc must be greater than 0")

    pairs = payroll_service.build_salary_components(
        principal.db, principal.tenant_id, structure, ctc
    )
    return [
        SalaryComponentAmountOut(
            component_id=c.id,
            code=c.code,
            name=c.name,
            component_type=c.component_type,
            monthly_amount=amount,
        )
        for c, amount in pairs
    ]


# --------------------------------------------------------------- employee salary


@router.get("/salaries/{employee_id}", response_model=list[EmployeeSalaryOut])
def employee_salary_history(employee_id: int, principal: SalaryRead):
    employee_service.require_employee(principal.db, principal.tenant_id, employee_id)
    rows = principal.db.scalars(
        select(EmployeeSalary)
        .where(EmployeeSalary.employee_id == employee_id)
        .order_by(EmployeeSalary.effective_from.desc())
    )
    return [salary_out(s) for s in rows]


@router.post(
    "/salaries/{employee_id}", response_model=EmployeeSalaryOut, status_code=status.HTTP_201_CREATED
)
def assign_salary(
    employee_id: int, payload: EmployeeSalaryCreate, principal: SalaryManage
):
    employee = employee_service.require_employee(principal.db, principal.tenant_id, employee_id)
    salary = payroll_service.assign_salary(principal.db, employee, payload)
    notification_service.audit(
        principal.db,
        company_id=principal.tenant_id,
        user_id=principal.user_id,
        action="salary.assign",
        entity_type="employee_salary",
        entity_id=salary.id,
        changes={"employee_id": employee_id, "ctc": float(salary.ctc)},
    )
    principal.db.commit()
    principal.db.refresh(salary)
    return salary_out(salary)


@router.get("/salaries/me/current", response_model=EmployeeSalaryOut)
def my_salary(principal: CurrentUser):
    principal.require(P.PAYROLL_READ_SELF)
    employee = principal.employee_or_404
    salary = principal.db.scalar(
        select(EmployeeSalary)
        .where(EmployeeSalary.employee_id == employee.id, EmployeeSalary.is_active.is_(True))
        .order_by(EmployeeSalary.effective_from.desc())
    )
    if salary is None:
        raise NotFound("No salary structure has been assigned to you yet")
    return salary_out(salary)


# --------------------------------------------------------------- payroll runs


@router.get("/runs", response_model=Page[PayrollRunOut])
def list_runs(pagination: Pagination, principal: PayrollRead):
    stmt = (
        select(PayrollRun)
        .where(PayrollRun.company_id == principal.tenant_id)
        .order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
    )
    rows, total = paginate(principal.db, stmt, pagination)
    return build_page(rows, total, pagination)


@router.post("/runs", response_model=PayrollRunDetail, status_code=status.HTTP_201_CREATED)
def process_payroll(payload: PayrollRunCreate, principal: ProcessAccess):
    """Fetches employees, salaries and attendance, computes LOP, and drafts the payroll."""
    run, skipped = payroll_service.process_payroll(
        principal.db, principal.tenant_id, payload, principal.user_id
    )
    notification_service.audit(
        principal.db,
        company_id=principal.tenant_id,
        user_id=principal.user_id,
        action="payroll.process",
        entity_type="payroll_run",
        entity_id=run.id,
        changes={"month": run.month, "year": run.year, "skipped": skipped},
    )
    principal.db.commit()
    principal.db.refresh(run)
    detail = PayrollRunDetail.model_validate(run, from_attributes=True)
    detail.items = [item_out(i) for i in run.items]
    detail.notes = "; ".join(skipped) if skipped else run.notes
    return detail


def _require_run(principal, run_id: int) -> PayrollRun:
    run = principal.db.get(PayrollRun, run_id)
    if run is None or run.company_id != principal.tenant_id:
        raise NotFound("Payroll run not found")
    return run


@router.get("/runs/{run_id}", response_model=PayrollRunDetail)
def get_run(run_id: int, principal: PayrollRead):
    run = _require_run(principal, run_id)
    detail = PayrollRunDetail.model_validate(run, from_attributes=True)
    detail.items = [item_out(i) for i in run.items]
    return detail


@router.post("/runs/{run_id}/approve", response_model=PayrollRunOut)
def approve_run(run_id: int, principal: ApproveAccess):
    run = _require_run(principal, run_id)
    payroll_service.approve_payroll(principal.db, run, principal.user_id)
    principal.db.commit()
    principal.db.refresh(run)
    return run


@router.post("/runs/{run_id}/payslips", response_model=list[PayslipOut])
def generate_payslips(run_id: int, principal: ProcessAccess):
    run = _require_run(principal, run_id)
    payslips = payroll_service.generate_payslips(principal.db, run)
    principal.db.commit()
    for payslip in payslips:
        principal.db.refresh(payslip)
    return [payslip_out(p) for p in payslips]


@router.post("/runs/{run_id}/mark-paid", response_model=PayrollRunOut)
def mark_paid(run_id: int, principal: ApproveAccess):
    run = _require_run(principal, run_id)
    if run.status != PayrollStatus.APPROVED:
        raise BadRequest("Only an approved payroll can be marked as paid")
    run.status = PayrollStatus.PAID
    principal.db.commit()
    principal.db.refresh(run)
    return run


@router.delete("/runs/{run_id}", response_model=Message)
def delete_run(run_id: int, principal: ProcessAccess):
    run = _require_run(principal, run_id)
    if run.status in (PayrollStatus.APPROVED, PayrollStatus.PAID):
        raise BadRequest("An approved or paid payroll cannot be deleted")
    principal.db.delete(run)
    principal.db.commit()
    return Message(message="Payroll run deleted")


# --------------------------------------------------------------- payslips


@router.get("/payslips/me", response_model=list[PayslipOut])
def my_payslips(principal: CurrentUser, year: int | None = None):
    principal.require(P.PAYROLL_READ_SELF)
    employee = principal.employee_or_404
    stmt = select(Payslip).where(Payslip.employee_id == employee.id)
    if year:
        stmt = stmt.where(Payslip.year == year)
    rows = principal.db.scalars(stmt.order_by(Payslip.year.desc(), Payslip.month.desc()))
    return [payslip_out(p) for p in rows]


@router.get("/payslips/{payslip_id}", response_model=PayslipOut)
def get_payslip(payslip_id: int, principal: CurrentUser):
    payslip = principal.db.get(Payslip, payslip_id)
    if payslip is None or payslip.company_id != principal.tenant_id:
        raise NotFound("Payslip not found")

    if not principal.has(P.PAYROLL_READ_ALL):
        me = principal.employee
        if me is None or payslip.employee_id != me.id:
            raise Forbidden("You can only view your own payslips")
    return payslip_out(payslip)


@router.get("/runs/{run_id}/payslips", response_model=list[PayslipOut])
def run_payslips(run_id: int, principal: PayrollRead):
    _require_run(principal, run_id)
    rows = principal.db.scalars(select(Payslip).where(Payslip.payroll_run_id == run_id))
    return [payslip_out(p) for p in rows]
