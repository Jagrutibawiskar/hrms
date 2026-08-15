from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.core.deps import Perm, client_ip
from app.core.exceptions import Forbidden
from app.core.pagination import Page, Pagination, build_page, paginate
from app.core.rbac import P
from app.models.attendance import Attendance
from app.models.employee import EmployeeEmploymentDetail
from app.models.enums import AttendanceStatus
from app.schemas.attendance import (
    AttendanceOut,
    AttendanceRegularize,
    AttendanceSummary,
    CheckInRequest,
    CheckOutRequest,
    TodayAttendance,
)
from app.schemas.common import Message
from app.services import attendance_service, employee_service
from app.utils.dates import as_utc, today

router = APIRouter(prefix="/attendance", tags=["Attendance"])

SelfAccess = Perm(P.ATTENDANCE_MARK_SELF)
ReadAccess = Perm(
    P.ATTENDANCE_READ_ALL, P.ATTENDANCE_READ_TEAM, P.ATTENDANCE_READ_SELF
)
ManageAccess = Perm(P.ATTENDANCE_MANAGE)


def to_out(record: Attendance) -> AttendanceOut:
    return AttendanceOut(
        id=record.id,
        employee_id=record.employee_id,
        employee_name=record.employee.full_name if record.employee else None,
        employee_code=record.employee.employee_code if record.employee else None,
        date=record.date,
        check_in=as_utc(record.check_in),
        check_out=as_utc(record.check_out),
        working_hours=float(record.working_hours),
        status=record.status,
        is_late=record.is_late,
        late_minutes=int(record.late_minutes or 0),
        is_regularized=record.is_regularized,
        remarks=record.remarks,
    )


def _scope_ids(principal) -> list[int] | None:
    if principal.has(P.ATTENDANCE_READ_ALL):
        return None
    if principal.has(P.ATTENDANCE_READ_TEAM):
        return principal.team_employee_ids()
    me = principal.employee
    return [me.id] if me else []


@router.get("/today", response_model=TodayAttendance)
def today_status(principal: SelfAccess):
    return attendance_service.today_status(principal.db, principal.employee_or_404)


@router.post("/check-in", response_model=AttendanceOut)
def check_in(payload: CheckInRequest, request: Request, principal: SelfAccess):
    record = attendance_service.check_in(
        principal.db,
        principal.employee_or_404,
        is_wfh=payload.is_wfh,
        remarks=payload.remarks,
        ip=client_ip(request),
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    principal.db.commit()
    principal.db.refresh(record)
    return to_out(record)


@router.post("/check-out", response_model=AttendanceOut)
def check_out(payload: CheckOutRequest, request: Request, principal: SelfAccess):
    record = attendance_service.check_out(
        principal.db,
        principal.employee_or_404,
        remarks=payload.remarks,
        ip=client_ip(request),
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    principal.db.commit()
    principal.db.refresh(record)
    return to_out(record)


@router.get("/me", response_model=list[AttendanceOut])
def my_attendance(
    principal: SelfAccess,
    from_date: date | None = None,
    to_date: date | None = None,
):
    employee = principal.employee_or_404
    end = to_date or today()
    start = from_date or end.replace(day=1)
    records = principal.db.scalars(
        select(Attendance)
        .where(
            Attendance.employee_id == employee.id,
            Attendance.date >= start,
            Attendance.date <= end,
        )
        .order_by(Attendance.date.desc())
    )
    return [to_out(r) for r in records]


@router.get("/me/summary", response_model=AttendanceSummary)
def my_summary(
    principal: SelfAccess,
    from_date: date | None = None,
    to_date: date | None = None,
):
    employee = principal.employee_or_404
    end = to_date or today()
    start = from_date or end.replace(day=1)
    records = list(
        principal.db.scalars(
            select(Attendance).where(
                Attendance.employee_id == employee.id,
                Attendance.date >= start,
                Attendance.date <= end,
            )
        )
    )
    return attendance_service.summarize(records, start, end)


@router.get("", response_model=Page[AttendanceOut])
def list_attendance(
    pagination: Pagination,
    principal: ReadAccess,
    employee_id: int | None = None,
    department_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    status_: Annotated[AttendanceStatus | None, Query(alias="status")] = None,
):
    db = principal.db
    end = to_date or today()
    start = from_date or end.replace(day=1)

    stmt = select(Attendance).where(
        Attendance.company_id == principal.tenant_id,
        Attendance.date >= start,
        Attendance.date <= end,
    )

    allowed = _scope_ids(principal)
    if allowed is not None:
        stmt = stmt.where(Attendance.employee_id.in_(allowed or [-1]))
    if employee_id:
        if allowed is not None and employee_id not in allowed:
            raise Forbidden("You do not have access to this employee's attendance")
        stmt = stmt.where(Attendance.employee_id == employee_id)
    if department_id:
        stmt = stmt.where(
            Attendance.employee_id.in_(
                select(EmployeeEmploymentDetail.employee_id).where(
                    EmployeeEmploymentDetail.department_id == department_id
                )
            )
        )
    if status_:
        stmt = stmt.where(Attendance.status == status_)

    stmt = stmt.order_by(Attendance.date.desc(), Attendance.employee_id)
    rows, total = paginate(db, stmt, pagination)
    return build_page([to_out(r) for r in rows], total, pagination)


@router.get("/summary/{employee_id}", response_model=AttendanceSummary)
def employee_summary(
    employee_id: int,
    principal: ReadAccess,
    from_date: date | None = None,
    to_date: date | None = None,
):
    allowed = _scope_ids(principal)
    if allowed is not None and employee_id not in allowed:
        raise Forbidden("You do not have access to this employee's attendance")

    employee_service.require_employee(principal.db, principal.tenant_id, employee_id)
    end = to_date or today()
    start = from_date or end.replace(day=1)
    records = list(
        principal.db.scalars(
            select(Attendance).where(
                Attendance.employee_id == employee_id,
                Attendance.date >= start,
                Attendance.date <= end,
            )
        )
    )
    return attendance_service.summarize(records, start, end)


@router.put("/{employee_id}/{day}", response_model=AttendanceOut)
def regularize(
    employee_id: int,
    day: date,
    payload: AttendanceRegularize,
    principal: ManageAccess,
):
    """HR override for a single day (missed punch, on-duty, correction)."""
    employee = employee_service.require_employee(principal.db, principal.tenant_id, employee_id)
    record = attendance_service.regularize(
        principal.db, employee, day, payload, principal.user_id
    )
    principal.db.commit()
    principal.db.refresh(record)
    return to_out(record)


@router.post("/backfill", response_model=Message)
def backfill(
    principal: ManageAccess,
    day: date | None = None,
):
    """Fills missing rows for a day as ABSENT / WEEKEND / HOLIDAY / LEAVE.

    Idempotent, so it is safe to run from a nightly scheduler.
    """
    target = day or (today() - timedelta(days=1))
    created = attendance_service.backfill_absents(principal.db, principal.tenant_id, target)
    principal.db.commit()
    return Message(message=f"{created} attendance record(s) created for {target}")
