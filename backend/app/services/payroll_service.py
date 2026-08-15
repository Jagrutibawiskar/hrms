from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequest, Conflict, NotFound
from app.models.attendance import Attendance
from app.models.company import Company
from app.models.compliance import CompanyCompliance
from app.models.employee import Employee
from app.models.enums import (
    AttendanceStatus,
    CalculationType,
    ComponentType,
    EmployeeStatus,
    NotificationEvent,
    PayrollStatus,
    RoleName,
)
from app.models.payroll import (
    EmployeeSalary,
    EmployeeSalaryComponent,
    PayrollItem,
    PayrollRun,
    Payslip,
    SalaryComponent,
    SalaryStructure,
)
from app.services import notification_service
from app.services.calendar_service import (
    count_working_days,
    employee_location_id,
    get_work_policy,
)
from app.services.leave_service import approved_leave_days
from app.utils.dates import month_bounds, utcnow

TWO_DP = Decimal("0.01")


def money(value) -> float:
    return float(Decimal(str(value or 0)).quantize(TWO_DP, rounding=ROUND_HALF_UP))


# --------------------------------------------------------------- salary setup


def resolve_component_amount(
    component: SalaryComponent, value: float, ctc: float, basic_monthly: float, gross: float
) -> float:
    """Turns a structure rule into a concrete monthly amount."""
    match component.calculation_type:
        case CalculationType.FIXED:
            return money(value)
        case CalculationType.PERCENT_OF_BASIC:
            return money(basic_monthly * value / 100)
        case CalculationType.PERCENT_OF_CTC:
            return money(ctc / 12 * value / 100)
        case CalculationType.PERCENT_OF_GROSS:
            return money(gross * value / 100)
    return 0.0


def build_salary_components(
    db: Session, company_id: int, structure: SalaryStructure | None, ctc: float
) -> list[tuple[SalaryComponent, float]]:
    """Expands a structure into (component, monthly_amount) pairs.

    BASIC is resolved first because other components can be a percentage of it,
    then earnings (which fix the gross), then deductions.
    """
    if structure is None:
        raise BadRequest("A salary structure is required to derive component amounts")

    rows = sorted(structure.components, key=lambda c: c.component.display_order)
    monthly_ctc = ctc / 12

    basic_monthly = 0.0
    for row in rows:
        if row.component.code.upper() == "BASIC":
            basic_monthly = resolve_component_amount(
                row.component, float(row.value), ctc, monthly_ctc, 0
            )
            break

    resolved: list[tuple[SalaryComponent, float]] = []
    gross = 0.0
    for row in rows:
        if row.component.component_type != ComponentType.EARNING:
            continue
        amount = (
            basic_monthly
            if row.component.code.upper() == "BASIC"
            else resolve_component_amount(
                row.component, float(row.value), ctc, basic_monthly, gross
            )
        )
        resolved.append((row.component, amount))
        gross += amount

    for row in rows:
        if row.component.component_type != ComponentType.DEDUCTION:
            continue
        amount = resolve_component_amount(
            row.component, float(row.value), ctc, basic_monthly, gross
        )
        resolved.append((row.component, amount))

    return resolved


def assign_salary(db: Session, employee: Employee, payload) -> EmployeeSalary:
    structure = None
    if payload.structure_id:
        structure = db.get(SalaryStructure, payload.structure_id)
        if structure is None or structure.company_id != employee.company_id:
            raise NotFound("Salary structure not found")

    if payload.components:
        pairs = []
        for item in payload.components:
            component = db.get(SalaryComponent, item.component_id)
            if component is None or component.company_id != employee.company_id:
                raise BadRequest(f"Salary component {item.component_id} not found")
            pairs.append((component, money(item.monthly_amount)))
    else:
        pairs = build_salary_components(db, employee.company_id, structure, payload.ctc)

    gross = money(sum(a for c, a in pairs if c.component_type == ComponentType.EARNING))
    deductions = money(sum(a for c, a in pairs if c.component_type == ComponentType.DEDUCTION))

    # Close the previous record rather than deleting it — salary history matters.
    previous = db.scalar(
        select(EmployeeSalary).where(
            EmployeeSalary.employee_id == employee.id, EmployeeSalary.is_active.is_(True)
        )
    )
    if previous is not None:
        if payload.effective_from <= previous.effective_from:
            raise BadRequest(
                f"effective_from must be after the current structure's start "
                f"({previous.effective_from})"
            )
        previous.is_active = False
        previous.effective_to = payload.effective_from

    salary = EmployeeSalary(
        company_id=employee.company_id,
        employee_id=employee.id,
        structure_id=structure.id if structure else None,
        ctc=money(payload.ctc),
        gross_monthly=gross,
        deductions_monthly=deductions,
        net_monthly=money(gross - deductions),
        effective_from=payload.effective_from,
        is_active=True,
        payment_mode=payload.payment_mode,
        bank_account_number=payload.bank_account_number,
        bank_ifsc=payload.bank_ifsc,
    )
    db.add(salary)
    db.flush()

    for component, amount in pairs:
        db.add(
            EmployeeSalaryComponent(
                employee_salary_id=salary.id, component_id=component.id, monthly_amount=amount
            )
        )
    db.flush()
    db.refresh(salary)
    return salary


def active_salary(db: Session, employee_id: int, on_date: date) -> EmployeeSalary | None:
    return db.scalar(
        select(EmployeeSalary)
        .where(
            EmployeeSalary.employee_id == employee_id,
            EmployeeSalary.effective_from <= on_date,
        )
        .order_by(EmployeeSalary.effective_from.desc(), EmployeeSalary.id.desc())
    )


# --------------------------------------------------------------- payroll run


def compute_lop(
    db: Session, employee: Employee, start: date, end: date, working_days: int
) -> tuple[float, dict]:
    """Loss-of-pay days, with the breakdown that produced them.

    LOP = unmarked absences + approved *unpaid* leave + half of each half-day.
    Approved paid leave never costs pay, which is why it isn't in this sum.
    """
    records = list(
        db.scalars(
            select(Attendance).where(
                Attendance.employee_id == employee.id,
                Attendance.date >= start,
                Attendance.date <= end,
            )
        )
    )
    absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
    half_days = sum(1 for r in records if r.status == AttendanceStatus.HALF_DAY)
    present = sum(
        1
        for r in records
        if r.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.WFH)
    )

    paid_leave, unpaid_leave = approved_leave_days(db, employee.id, start, end)

    raw = absent + unpaid_leave + (half_days * 0.5)
    lop = float(min(raw, working_days))

    breakdown = {
        "absent_days": float(absent),
        "unpaid_leave_days": float(unpaid_leave),
        "half_days": float(half_days),
        "paid_leave_days": float(paid_leave),
        "present_days": float(present),
    }
    return lop, breakdown


def _prorate(amount: float, paid_days: float, working_days: float, prorate: bool) -> float:
    if not prorate or working_days <= 0 or paid_days >= working_days:
        return money(amount)
    return money(amount * paid_days / working_days)


def build_payroll_item(
    db: Session, run: PayrollRun, employee: Employee, start: date, end: date
) -> PayrollItem | None:
    salary = active_salary(db, employee.id, end)
    if salary is None:
        return None

    policy = get_work_policy(db, employee.company_id, employee)
    working_days = count_working_days(
        db, employee.company_id, start, end, policy, employee_location_id(employee)
    )
    if working_days == 0:
        return None

    lop_days, lop_breakdown = compute_lop(db, employee, start, end, working_days)
    paid_days = max(working_days - lop_days, 0)

    # Statutory deductions the company has switched off shouldn't appear at all.
    compliance = db.scalar(
        select(CompanyCompliance).where(CompanyCompliance.company_id == run.company_id)
    )
    disabled: set[str] = set()
    if compliance is not None:
        if not compliance.pf_enabled:
            disabled.add("PF")
        if not compliance.esi_enabled:
            disabled.add("ESI")
        if not compliance.pt_enabled:
            disabled.add("PT")
        if not compliance.tds_enabled:
            disabled.add("TDS")

    earnings, deductions = [], []
    gross = total_deductions = 0.0

    for row in sorted(salary.components, key=lambda c: c.component.display_order):
        component = row.component
        if component.code.upper() in disabled:
            continue
        amount = _prorate(
            float(row.monthly_amount), paid_days, working_days, component.prorate_on_lop
        )
        line = {"code": component.code, "name": component.name, "amount": amount}
        if component.component_type == ComponentType.EARNING:
            earnings.append(line)
            gross += amount
        else:
            deductions.append(line)
            total_deductions += amount

    item = PayrollItem(
        company_id=run.company_id,
        payroll_run_id=run.id,
        employee_id=employee.id,
        working_days=working_days,
        paid_days=paid_days,
        lop_days=lop_days,
        gross_earnings=money(gross),
        total_deductions=money(total_deductions),
        net_pay=money(gross - total_deductions),
        earnings_breakdown=earnings,
        deductions_breakdown=deductions,
        lop_breakdown=lop_breakdown,
    )
    db.add(item)
    return item


def process_payroll(
    db: Session, company_id: int, payload, actor_user_id: int
) -> tuple[PayrollRun, list[str]]:
    existing = db.scalar(
        select(PayrollRun).where(
            PayrollRun.company_id == company_id,
            PayrollRun.year == payload.year,
            PayrollRun.month == payload.month,
        )
    )
    # A run that hasn't been approved yet can be recalculated — that's the whole point
    # of the review step, since HR often fixes attendance and re-runs. Once approved or
    # paid the numbers are final.
    if existing is not None and existing.status not in (
        PayrollStatus.DRAFT,
        PayrollStatus.PENDING_REVIEW,
    ):
        raise Conflict(
            f"Payroll for {payload.month}/{payload.year} is already "
            f"{existing.status.value.lower()} and can no longer be recalculated"
        )

    start, end = month_bounds(payload.year, payload.month)

    stmt = select(Employee).where(
        Employee.company_id == company_id,
        Employee.status.in_(
            [EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION, EmployeeStatus.NOTICE_PERIOD]
        ),
    )
    if payload.employee_ids:
        stmt = stmt.where(Employee.id.in_(payload.employee_ids))
    employees = list(db.scalars(stmt))
    if not employees:
        raise BadRequest("No active employees to process payroll for")

    run = existing
    if run is None:
        run = PayrollRun(company_id=company_id, month=payload.month, year=payload.year)
        db.add(run)
        db.flush()
    else:
        for item in list(run.items):
            db.delete(item)
        db.flush()

    run.notes = payload.notes
    skipped: list[str] = []
    items: list[PayrollItem] = []

    for employee in employees:
        if employee.employment and employee.employment.joining_date > end:
            skipped.append(f"{employee.employee_code}: joined after this period")
            continue
        item = build_payroll_item(db, run, employee, start, end)
        if item is None:
            skipped.append(f"{employee.employee_code}: no salary structure assigned")
            continue
        items.append(item)

    if not items:
        raise BadRequest(
            "No payroll could be generated. Assign salary structures first. "
            + "; ".join(skipped[:5])
        )

    run.employee_count = len(items)
    run.total_gross = money(sum(float(i.gross_earnings) for i in items))
    run.total_deductions = money(sum(float(i.total_deductions) for i in items))
    run.total_net = money(sum(float(i.net_pay) for i in items))
    run.status = PayrollStatus.PENDING_REVIEW
    run.processed_by_user_id = actor_user_id
    run.processed_at = utcnow()

    db.flush()
    return run, skipped


def approve_payroll(db: Session, run: PayrollRun, actor_user_id: int) -> PayrollRun:
    if run.status != PayrollStatus.PENDING_REVIEW:
        raise BadRequest(f"Only a PENDING_REVIEW payroll can be approved (current: {run.status.value})")
    run.status = PayrollStatus.APPROVED
    run.approved_by_user_id = actor_user_id
    run.approved_at = utcnow()

    notification_service.notify_roles(
        db,
        run.company_id,
        [RoleName.HR, RoleName.COMPANY_ADMIN],
        event=NotificationEvent.PAYROLL_PROCESSED,
        title="Payroll approved",
        message=f"Payroll for {run.month}/{run.year} was approved. Net payable: {run.total_net}.",
        entity_type="payroll_run",
        entity_id=run.id,
        action_url=f"/payroll/{run.id}",
    )
    return run


def generate_payslips(db: Session, run: PayrollRun) -> list[Payslip]:
    if run.status not in (PayrollStatus.APPROVED, PayrollStatus.PAID):
        raise BadRequest("Payslips can only be generated for an approved payroll")

    payslips: list[Payslip] = []
    for item in run.items:
        existing = db.scalar(select(Payslip).where(Payslip.payroll_item_id == item.id))
        if existing is not None:
            payslips.append(existing)
            continue

        employee = item.employee
        employment = employee.employment
        company = db.get(Company, run.company_id)
        snapshot = {
            "company": {
                "name": company.name if company else None,
                "address": company.address if company else None,
                "city": company.city if company else None,
                "state": company.state if company else None,
                "currency": company.currency if company else "INR",
                # Rendered at the top of the payslip.
                "logo_path": company.logo_path if company else None,
            },
            "employee": {
                "id": employee.id,
                "code": employee.employee_code,
                "name": employee.full_name,
                "email": employee.work_email,
                "department": employment.department.name
                if employment and employment.department
                else None,
                "designation": employment.designation.name
                if employment and employment.designation
                else None,
                "joining_date": str(employment.joining_date) if employment else None,
            },
            "period": {"month": run.month, "year": run.year},
            "days": {
                "working_days": float(item.working_days),
                "paid_days": float(item.paid_days),
                "lop_days": float(item.lop_days),
                **(item.lop_breakdown or {}),
            },
            "earnings": item.earnings_breakdown,
            "deductions": item.deductions_breakdown,
            "totals": {
                "gross_earnings": float(item.gross_earnings),
                "total_deductions": float(item.total_deductions),
                "net_pay": float(item.net_pay),
            },
        }

        payslip = Payslip(
            company_id=run.company_id,
            payroll_run_id=run.id,
            payroll_item_id=item.id,
            employee_id=employee.id,
            payslip_number=f"PS-{run.year}{run.month:02d}-{employee.employee_code}-{run.id}",
            month=run.month,
            year=run.year,
            net_pay=item.net_pay,
            snapshot=snapshot,
            generated_at=utcnow(),
        )
        db.add(payslip)
        payslips.append(payslip)

        notification_service.notify_employee(
            db,
            employee,
            event=NotificationEvent.PAYSLIP_GENERATED,
            title="Payslip available",
            message=f"Your payslip for {run.month}/{run.year} is ready. Net pay: {item.net_pay}.",
            entity_type="payslip",
            entity_id=None,
            action_url="/payslips",
        )

    db.flush()
    return payslips
