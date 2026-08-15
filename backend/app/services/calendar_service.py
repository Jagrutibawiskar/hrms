"""Shared working-day / holiday calendar used by attendance, leave and payroll."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee, EmployeeEmploymentDetail
from app.models.policy import Holiday, WorkPolicy
from app.utils.dates import date_range


def get_work_policy(db: Session, company_id: int, employee: Employee | None = None) -> WorkPolicy | None:
    """The employee's assigned policy, else the company default, else any active one."""
    if employee is not None and employee.employment and employee.employment.work_policy_id:
        policy = db.get(WorkPolicy, employee.employment.work_policy_id)
        if policy and policy.company_id == company_id:
            return policy

    return db.scalar(
        select(WorkPolicy)
        .where(WorkPolicy.company_id == company_id, WorkPolicy.is_active.is_(True))
        .order_by(WorkPolicy.is_default.desc(), WorkPolicy.id)
    )


def is_working_day(policy: WorkPolicy | None, day: date) -> bool:
    if policy is None:
        return day.isoweekday() <= 5
    return day.isoweekday() in (policy.working_days or [])


def holiday_map(
    db: Session, company_id: int, start: date, end: date, location_id: int | None = None
) -> dict[date, Holiday]:
    """Holidays keyed by date. Company-wide holidays (location_id NULL) always apply."""
    stmt = select(Holiday).where(
        Holiday.company_id == company_id, Holiday.date >= start, Holiday.date <= end
    )
    holidays = list(db.scalars(stmt))
    result: dict[date, Holiday] = {}
    for h in holidays:
        if h.location_id is None or h.location_id == location_id:
            result.setdefault(h.date, h)
    return result


def employee_location_id(employee: Employee | None) -> int | None:
    if employee and employee.employment:
        return employee.employment.location_id
    return None


def count_working_days(
    db: Session,
    company_id: int,
    start: date,
    end: date,
    policy: WorkPolicy | None,
    location_id: int | None = None,
) -> int:
    """Calendar days in [start, end] that are neither weekly-off nor a holiday."""
    holidays = holiday_map(db, company_id, start, end, location_id)
    return sum(
        1 for day in date_range(start, end) if is_working_day(policy, day) and day not in holidays
    )


def working_days_between(
    db: Session, employee: Employee, start: date, end: date
) -> tuple[int, WorkPolicy | None]:
    policy = get_work_policy(db, employee.company_id, employee)
    loc = employee_location_id(employee)
    return count_working_days(db, employee.company_id, start, end, policy, loc), policy


def employees_with_details(db: Session, company_id: int):
    """Employees joined to their employment row — the common listing base query."""
    return (
        select(Employee)
        .join(
            EmployeeEmploymentDetail,
            EmployeeEmploymentDetail.employee_id == Employee.id,
            isouter=True,
        )
        .where(Employee.company_id == company_id)
    )
