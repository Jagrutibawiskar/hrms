from datetime import timedelta

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.deps import CurrentUser, Perm
from app.core.rbac import P
from app.models.attendance import Attendance
from app.models.employee import Employee, EmployeeEmploymentDetail, EmployeePersonalDetail
from app.models.enums import AttendanceStatus, EmployeeStatus, LeaveStatus, PayrollStatus
from app.models.leave import LeaveRequest
from app.models.notification import Notification
from app.models.payroll import PayrollRun
from app.models.policy import Holiday
from app.schemas.misc import (
    DashboardCounts,
    EmployeeDashboard,
    HrDashboard,
    MiniEmployee,
    MiniHoliday,
    PendingItems,
)
from app.services import attendance_service, leave_service
from app.utils.dates import today

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

ACTIVE_STATUSES = [
    EmployeeStatus.ACTIVE,
    EmployeeStatus.PROBATION,
    EmployeeStatus.NOTICE_PERIOD,
]


@router.get("/hr", response_model=HrDashboard)
def hr_dashboard(principal: Perm(P.DASHBOARD_HR)):
    db, tenant, day = principal.db, principal.tenant_id, today()

    total = db.scalar(select(func.count(Employee.id)).where(Employee.company_id == tenant)) or 0
    active = (
        db.scalar(
            select(func.count(Employee.id)).where(
                Employee.company_id == tenant, Employee.status.in_(ACTIVE_STATUSES)
            )
        )
        or 0
    )

    status_counts = dict(
        db.execute(
            select(Attendance.status, func.count(Attendance.id))
            .where(Attendance.company_id == tenant, Attendance.date == day)
            .group_by(Attendance.status)
        ).all()
    )
    present = status_counts.get(AttendanceStatus.PRESENT, 0)
    late = status_counts.get(AttendanceStatus.LATE, 0)
    wfh = status_counts.get(AttendanceStatus.WFH, 0)
    on_leave = status_counts.get(AttendanceStatus.LEAVE, 0) + status_counts.get(
        AttendanceStatus.HALF_DAY, 0
    )
    marked = present + late + wfh + on_leave + status_counts.get(AttendanceStatus.ABSENT, 0)
    # Employees with no row yet today are counted as not-yet-present, not absent.
    absent = max(active - present - late - wfh - on_leave, 0) if marked < active else (
        status_counts.get(AttendanceStatus.ABSENT, 0)
    )

    pending_leaves = (
        db.scalar(
            select(func.count(LeaveRequest.id)).where(
                LeaveRequest.company_id == tenant, LeaveRequest.status == LeaveStatus.PENDING
            )
        )
        or 0
    )
    pending_payroll = (
        db.scalar(
            select(func.count(PayrollRun.id)).where(
                PayrollRun.company_id == tenant,
                PayrollRun.status == PayrollStatus.PENDING_REVIEW,
            )
        )
        or 0
    )

    joiners = db.execute(
        select(Employee, EmployeeEmploymentDetail)
        .join(EmployeeEmploymentDetail, EmployeeEmploymentDetail.employee_id == Employee.id)
        .where(
            Employee.company_id == tenant,
            EmployeeEmploymentDetail.joining_date >= day - timedelta(days=30),
        )
        .order_by(EmployeeEmploymentDetail.joining_date.desc())
        .limit(10)
    ).all()

    new_joiners = [
        MiniEmployee(
            id=e.id,
            employee_code=e.employee_code,
            full_name=e.full_name,
            department_name=d.department.name if d.department else None,
            designation_name=d.designation.name if d.designation else None,
            date=d.joining_date,
        )
        for e, d in joiners
    ]

    birthdays = []
    window = {(day + timedelta(days=i)).strftime("%m-%d") for i in range(0, 31)}
    rows = db.execute(
        select(Employee, EmployeePersonalDetail)
        .join(EmployeePersonalDetail, EmployeePersonalDetail.employee_id == Employee.id)
        .where(
            Employee.company_id == tenant,
            Employee.status.in_(ACTIVE_STATUSES),
            EmployeePersonalDetail.date_of_birth.is_not(None),
        )
    ).all()
    for employee, personal in rows:
        if personal.date_of_birth.strftime("%m-%d") in window:
            birthdays.append(
                MiniEmployee(
                    id=employee.id,
                    employee_code=employee.employee_code,
                    full_name=employee.full_name,
                    date=personal.date_of_birth,
                )
            )
    birthdays.sort(key=lambda b: b.date.strftime("%m-%d"))

    holidays = db.scalars(
        select(Holiday)
        .where(Holiday.company_id == tenant, Holiday.date >= day)
        .order_by(Holiday.date)
        .limit(5)
    )

    recent = db.scalars(
        select(LeaveRequest)
        .where(LeaveRequest.company_id == tenant, LeaveRequest.status == LeaveStatus.PENDING)
        .order_by(LeaveRequest.applied_at.desc())
        .limit(5)
    )

    return HrDashboard(
        counts=DashboardCounts(
            total_employees=total,
            active_employees=active,
            present_today=present + late,
            absent_today=absent,
            on_leave_today=on_leave,
            late_today=late,
            wfh_today=wfh,
        ),
        pending=PendingItems(
            pending_leave_requests=pending_leaves, pending_payroll_runs=pending_payroll
        ),
        new_joiners=new_joiners,
        upcoming_birthdays=birthdays[:10],
        upcoming_holidays=[
            MiniHoliday(id=h.id, name=h.name, date=h.date, holiday_type=h.holiday_type.value)
            for h in holidays
        ],
        recent_leave_requests=[
            {
                "id": r.id,
                "employee_name": r.employee.full_name if r.employee else None,
                "leave_type": r.leave_type.name if r.leave_type else None,
                "from_date": str(r.from_date),
                "to_date": str(r.to_date),
                "days": float(r.days),
                "applied_at": r.applied_at.isoformat(),
            }
            for r in recent
        ],
    )


@router.get("/me", response_model=EmployeeDashboard)
def employee_dashboard(principal: CurrentUser):
    db, tenant, day = principal.db, principal.tenant_id, today()
    employee = principal.employee_or_404

    balances = leave_service.get_balances(db, employee)
    db.commit()

    pending = (
        db.scalar(
            select(func.count(LeaveRequest.id)).where(
                LeaveRequest.employee_id == employee.id,
                LeaveRequest.status == LeaveStatus.PENDING,
            )
        )
        or 0
    )

    month_start = day.replace(day=1)
    records = list(
        db.scalars(
            select(Attendance).where(
                Attendance.employee_id == employee.id,
                Attendance.date >= month_start,
                Attendance.date <= day,
            )
        )
    )

    holidays = db.scalars(
        select(Holiday)
        .where(Holiday.company_id == tenant, Holiday.date >= day)
        .order_by(Holiday.date)
        .limit(5)
    )

    unread = (
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == principal.user_id, Notification.is_read.is_(False)
            )
        )
        or 0
    )

    status = attendance_service.today_status(db, employee)
    status["date"] = str(status["date"])
    status["server_time"] = status["server_time"].isoformat()
    status["check_in"] = status["check_in"].isoformat() if status["check_in"] else None
    status["check_out"] = status["check_out"].isoformat() if status["check_out"] else None
    status["status"] = status["status"].value if status["status"] else None

    return EmployeeDashboard(
        employee_id=employee.id,
        full_name=employee.full_name,
        today=status,
        leave_balances=[
            {
                "leave_type": b.leave_type.name,
                "code": b.leave_type.code,
                "used": float(b.used),
                "total": b.total,
                "available": b.available,
            }
            for b in balances
        ],
        pending_leaves=pending,
        upcoming_holidays=[
            MiniHoliday(id=h.id, name=h.name, date=h.date, holiday_type=h.holiday_type.value)
            for h in holidays
        ],
        unread_notifications=unread,
        attendance_this_month=attendance_service.summarize(records, month_start, day),
    )
