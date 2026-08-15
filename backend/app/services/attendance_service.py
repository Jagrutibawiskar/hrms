from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequest, Conflict
from app.models.attendance import Attendance, AttendanceLog
from app.models.company import Company
from app.models.employee import Employee
from app.models.enums import AttendanceLogType, AttendanceStatus, LeaveStatus
from app.models.leave import LeaveRequest
from app.models.policy import WorkPolicy
from app.utils.dates import as_utc, hours_between, month_bounds, today, utcnow

from app.services.calendar_service import (
    employee_location_id,
    get_work_policy,
    holiday_map,
    is_working_day,
)
from app.services.geofence_service import check_within_fence
from app.services.geofence_service import employee_location as _fence_location


def geofence_location(db: Session, employee: Employee):
    """The fenced office for this employee, or None when nothing is fenced."""
    location = _fence_location(db, employee)
    return location if location is not None and location.has_geofence else None


def _expected_start(day: date, policy: WorkPolicy | None) -> datetime:
    start = policy.start_time if policy else time(9, 30)
    return datetime.combine(day, start, tzinfo=timezone.utc)


def _derive_status(
    policy: WorkPolicy | None, hours: float, is_late: bool, is_wfh: bool
) -> AttendanceStatus:
    full = float(policy.full_day_hours) if policy else 8.0
    half = float(policy.half_day_hours) if policy else 4.0

    if hours <= 0:
        return AttendanceStatus.WFH if is_wfh else AttendanceStatus.PRESENT
    if hours < half:
        return AttendanceStatus.ABSENT
    if hours < full:
        return AttendanceStatus.HALF_DAY
    if is_wfh:
        return AttendanceStatus.WFH
    return AttendanceStatus.LATE if is_late else AttendanceStatus.PRESENT


def get_or_none(db: Session, employee_id: int, day: date) -> Attendance | None:
    return db.scalar(
        select(Attendance).where(Attendance.employee_id == employee_id, Attendance.date == day)
    )


def on_approved_leave(db: Session, employee_id: int, day: date) -> LeaveRequest | None:
    return db.scalar(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.from_date <= day,
            LeaveRequest.to_date >= day,
        )
    )


def check_in(
    db: Session,
    employee: Employee,
    is_wfh: bool = False,
    remarks: str | None = None,
    ip: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Attendance:
    day = today()
    now = utcnow()

    record = get_or_none(db, employee.id, day)
    if record is not None and record.check_in is not None:
        raise Conflict("You have already checked in today")

    if on_approved_leave(db, employee.id, day):
        raise BadRequest("You are on approved leave today")

    # Working from home is off-site by definition, so the fence doesn't apply.
    distance = None
    if not is_wfh:
        distance, _ = check_within_fence(db, employee, latitude, longitude)

    policy = get_work_policy(db, employee.company_id, employee)
    holidays = holiday_map(db, employee.company_id, day, day, employee_location_id(employee))

    expected = _expected_start(day, policy)
    grace = policy.late_grace_minutes if policy else 15
    late_by = max(int((now - expected).total_seconds() // 60), 0)
    is_late = late_by > grace

    if record is None:
        record = Attendance(company_id=employee.company_id, employee_id=employee.id, date=day)
        db.add(record)

    record.check_in = now
    record.is_late = is_late
    record.late_minutes = late_by if is_late else 0
    record.remarks = remarks
    record.check_in_lat = latitude
    record.check_in_lng = longitude
    record.check_in_distance_m = distance
    record.status = AttendanceStatus.WFH if is_wfh else (
        AttendanceStatus.LATE if is_late else AttendanceStatus.PRESENT
    )
    # A voluntary check-in on a holiday or weekly off is still recorded as worked time.
    if day in holidays and not is_wfh:
        record.remarks = remarks or f"Worked on holiday: {holidays[day].name}"
    elif not is_working_day(policy, day) and not is_wfh:
        record.remarks = remarks or "Worked on a weekly off"

    db.flush()
    db.add(
        AttendanceLog(
            company_id=employee.company_id,
            attendance_id=record.id,
            employee_id=employee.id,
            log_type=AttendanceLogType.CHECK_IN,
            logged_at=now,
            ip_address=ip,
        )
    )
    return record


def check_out(
    db: Session,
    employee: Employee,
    remarks: str | None = None,
    ip: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Attendance:
    day = today()
    now = utcnow()

    record = get_or_none(db, employee.id, day)
    if record is None or record.check_in is None:
        raise BadRequest("You have not checked in today")
    if record.check_out is not None:
        raise Conflict("You have already checked out today")

    if record.status != AttendanceStatus.WFH:
        check_within_fence(db, employee, latitude, longitude)

    record.check_out = now
    record.check_out_lat = latitude
    record.check_out_lng = longitude
    record.working_hours = hours_between(record.check_in, now)
    if remarks:
        record.remarks = remarks

    policy = get_work_policy(db, employee.company_id, employee)
    is_wfh = record.status == AttendanceStatus.WFH
    record.status = _derive_status(policy, float(record.working_hours), record.is_late, is_wfh)

    db.add(
        AttendanceLog(
            company_id=employee.company_id,
            attendance_id=record.id,
            employee_id=employee.id,
            log_type=AttendanceLogType.CHECK_OUT,
            logged_at=now,
            ip_address=ip,
        )
    )
    return record


def today_status(db: Session, employee: Employee) -> dict:
    day = today()
    record = get_or_none(db, employee.id, day)
    policy = get_work_policy(db, employee.company_id, employee)
    holidays = holiday_map(db, employee.company_id, day, day, employee_location_id(employee))
    leave = on_approved_leave(db, employee.id, day)

    company = db.get(Company, employee.company_id)
    geofenced = bool(company and company.geofence_enabled)
    fence_location = geofence_location(db, employee) if geofenced else None
    used, allowed = regularization_usage(db, employee, day)

    return {
        "date": day,
        "server_time": utcnow(),
        "geofence_enabled": geofenced and fence_location is not None,
        "geofence_location": fence_location.name if fence_location else None,
        "geofence_radius_m": fence_location.geofence_radius_m if fence_location else None,
        "regularizations_used": used,
        "regularizations_allowed": allowed,
        "checked_in": bool(record and record.check_in),
        "checked_out": bool(record and record.check_out),
        "check_in": as_utc(record.check_in) if record else None,
        "check_out": as_utc(record.check_out) if record else None,
        "working_hours": float(record.working_hours) if record else 0.0,
        "status": record.status if record else None,
        "is_working_day": is_working_day(policy, day) and day not in holidays,
        "is_holiday": day in holidays,
        "holiday_name": holidays[day].name if day in holidays else None,
        "on_leave": leave is not None,
    }


def regularization_usage(db: Session, employee: Employee, day: date) -> tuple[int, int]:
    """(used, allowed) regularizations for the calendar month containing `day`."""
    company = db.get(Company, employee.company_id)
    allowed = company.max_regularizations_per_month if company else 3
    start, end = month_bounds(day.year, day.month)
    used = (
        db.scalar(
            select(func.count(Attendance.id)).where(
                Attendance.employee_id == employee.id,
                Attendance.is_regularized.is_(True),
                Attendance.date >= start,
                Attendance.date <= end,
            )
        )
        or 0
    )
    return used, allowed


def regularize(
    db: Session, employee: Employee, day: date, payload, actor_user_id: int
) -> Attendance:
    record = get_or_none(db, employee.id, day)

    # Each employee gets a limited number of corrections per month. Re-editing a day
    # that is already regularized doesn't consume another allowance.
    if record is None or not record.is_regularized:
        used, allowed = regularization_usage(db, employee, day)
        if used >= allowed:
            raise BadRequest(
                f"{employee.full_name} has used all {allowed} attendance regularizations for "
                f"{day.strftime('%B %Y')}. No further corrections are allowed this month."
            )

    if record is None:
        record = Attendance(company_id=employee.company_id, employee_id=employee.id, date=day)
        db.add(record)

    if payload.check_in is not None:
        record.check_in = payload.check_in
    if payload.check_out is not None:
        record.check_out = payload.check_out
    if record.check_in and record.check_out:
        if as_utc(record.check_out) < as_utc(record.check_in):
            raise BadRequest("check_out cannot be before check_in")
        record.working_hours = hours_between(record.check_in, record.check_out)

    record.status = payload.status
    record.remarks = payload.remarks
    record.is_regularized = True
    record.regularized_by_user_id = actor_user_id
    db.flush()
    return record


def backfill_absents(db: Session, company_id: int, day: date) -> int:
    """Marks employees with no attendance row for `day` as ABSENT / WEEKEND / HOLIDAY.

    Idempotent — safe to run repeatedly, e.g. from a nightly job.
    """
    from app.models.enums import EmployeeStatus

    employees = list(
        db.scalars(
            select(Employee).where(
                Employee.company_id == company_id,
                Employee.status.in_(
                    [EmployeeStatus.ACTIVE, EmployeeStatus.PROBATION, EmployeeStatus.NOTICE_PERIOD]
                ),
            )
        )
    )
    created = 0
    for employee in employees:
        if get_or_none(db, employee.id, day) is not None:
            continue
        if employee.employment and employee.employment.joining_date > day:
            continue

        policy = get_work_policy(db, company_id, employee)
        holidays = holiday_map(db, company_id, day, day, employee_location_id(employee))

        if day in holidays:
            status = AttendanceStatus.HOLIDAY
        elif not is_working_day(policy, day):
            status = AttendanceStatus.WEEKEND
        elif on_approved_leave(db, employee.id, day):
            status = AttendanceStatus.LEAVE
        else:
            status = AttendanceStatus.ABSENT

        db.add(
            Attendance(
                company_id=company_id, employee_id=employee.id, date=day, status=status
            )
        )
        created += 1
    db.flush()
    return created


def summarize(records: list[Attendance], start: date, end: date) -> dict:
    counts = {status: 0 for status in AttendanceStatus}
    total_hours = 0.0
    for record in records:
        counts[record.status] += 1
        total_hours += float(record.working_hours)

    worked = counts[AttendanceStatus.PRESENT] + counts[AttendanceStatus.WFH] + counts[
        AttendanceStatus.LATE
    ]
    working_days = (
        worked
        + counts[AttendanceStatus.ABSENT]
        + counts[AttendanceStatus.HALF_DAY]
        + counts[AttendanceStatus.LEAVE]
    )
    return {
        "from_date": start,
        "to_date": end,
        "total_days": (end - start).days + 1,
        "working_days": working_days,
        "present": counts[AttendanceStatus.PRESENT],
        "absent": counts[AttendanceStatus.ABSENT],
        "half_day": counts[AttendanceStatus.HALF_DAY],
        "late": counts[AttendanceStatus.LATE],
        "leave": counts[AttendanceStatus.LEAVE],
        "holiday": counts[AttendanceStatus.HOLIDAY],
        "wfh": counts[AttendanceStatus.WFH],
        "weekend": counts[AttendanceStatus.WEEKEND],
        "total_hours": round(total_hours, 2),
        "average_hours": round(total_hours / worked, 2) if worked else 0.0,
    }
