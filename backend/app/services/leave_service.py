from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequest, Conflict, Forbidden, NotFound
from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.enums import (
    AttendanceStatus,
    LeaveStatus,
    NotificationEvent,
    RoleName,
)
from app.models.leave import LeaveRequest
from app.models.policy import LeaveBalance, LeaveType
from app.services import notification_service
from app.services.calendar_service import (
    employee_location_id,
    get_work_policy,
    holiday_map,
    is_working_day,
)
from app.utils.dates import date_range, today, utcnow


def current_year() -> int:
    return today().year


def ensure_leave_balances(db: Session, employee: Employee, year: int | None = None) -> list[LeaveBalance]:
    """Creates a zeroed-out balance row per active leave type, pre-filled with the quota."""
    year = year or current_year()
    leave_types = list(
        db.scalars(
            select(LeaveType).where(
                LeaveType.company_id == employee.company_id, LeaveType.is_active.is_(True)
            )
        )
    )
    existing = {
        b.leave_type_id: b
        for b in db.scalars(
            select(LeaveBalance).where(
                LeaveBalance.employee_id == employee.id, LeaveBalance.year == year
            )
        )
    }

    balances = []
    for lt in leave_types:
        balance = existing.get(lt.id)
        if balance is None:
            balance = LeaveBalance(
                company_id=employee.company_id,
                employee_id=employee.id,
                leave_type_id=lt.id,
                year=year,
                allocated=float(lt.annual_quota),
            )
            db.add(balance)
        balances.append(balance)

    db.flush()
    return balances


def get_balances(db: Session, employee: Employee, year: int | None = None) -> list[LeaveBalance]:
    year = year or current_year()
    ensure_leave_balances(db, employee, year)
    return list(
        db.scalars(
            select(LeaveBalance)
            .where(LeaveBalance.employee_id == employee.id, LeaveBalance.year == year)
            .order_by(LeaveBalance.leave_type_id)
        )
    )


def count_leave_days(
    db: Session, employee: Employee, start: date, end: date, is_half_day: bool
) -> float:
    """Leave days exclude weekly offs and holidays, so a Fri-Mon leave costs 2 days."""
    if is_half_day:
        return 0.5

    policy = get_work_policy(db, employee.company_id, employee)
    holidays = holiday_map(
        db, employee.company_id, start, end, employee_location_id(employee)
    )
    return float(
        sum(
            1
            for day in date_range(start, end)
            if is_working_day(policy, day) and day not in holidays
        )
    )


def _overlapping(db: Session, employee_id: int, start: date, end: date, exclude_id: int | None = None):
    stmt = select(LeaveRequest).where(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
        LeaveRequest.from_date <= end,
        LeaveRequest.to_date >= start,
    )
    if exclude_id:
        stmt = stmt.where(LeaveRequest.id != exclude_id)
    return db.scalar(stmt)


def _balance_for(db: Session, employee: Employee, leave_type_id: int, year: int) -> LeaveBalance:
    balance = db.scalar(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == employee.id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.year == year,
        )
    )
    if balance is None:
        ensure_leave_balances(db, employee, year)
        balance = db.scalar(
            select(LeaveBalance).where(
                LeaveBalance.employee_id == employee.id,
                LeaveBalance.leave_type_id == leave_type_id,
                LeaveBalance.year == year,
            )
        )
    if balance is None:
        raise BadRequest("No leave balance is configured for this leave type")
    return balance


def apply_leave(db: Session, employee: Employee, payload, attachment_path: str | None = None) -> LeaveRequest:
    leave_type = db.get(LeaveType, payload.leave_type_id)
    if leave_type is None or leave_type.company_id != employee.company_id:
        raise NotFound("Leave type not found")
    if not leave_type.is_active:
        raise BadRequest(f"{leave_type.name} is no longer available")
    if payload.is_half_day and not leave_type.allow_half_day:
        raise BadRequest(f"{leave_type.name} cannot be taken as a half day")
    if leave_type.requires_attachment and not attachment_path:
        raise BadRequest(f"{leave_type.name} requires a supporting document")

    if _overlapping(db, employee.id, payload.from_date, payload.to_date):
        raise Conflict("You already have a leave request covering these dates")

    days = count_leave_days(db, employee, payload.from_date, payload.to_date, payload.is_half_day)
    if days <= 0:
        raise BadRequest("The selected range contains no working days")

    year = payload.from_date.year
    balance = _balance_for(db, employee, leave_type.id, year)

    # Unpaid leave has no cap; paid leave must fit the remaining balance.
    if leave_type.is_paid and days > balance.available:
        raise BadRequest(
            f"Insufficient balance: requested {days} day(s), {balance.available} available"
        )

    manager_id = employee.employment.manager_id if employee.employment else None
    status = LeaveStatus.PENDING if leave_type.requires_approval else LeaveStatus.APPROVED

    request = LeaveRequest(
        company_id=employee.company_id,
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        from_date=payload.from_date,
        to_date=payload.to_date,
        is_half_day=payload.is_half_day,
        half_day_session=payload.half_day_session,
        days=days,
        reason=payload.reason,
        attachment_path=attachment_path,
        status=status,
        approver_id=manager_id,
    )
    db.add(request)
    db.flush()

    if status == LeaveStatus.APPROVED:
        balance.used = float(balance.used) + days
        _mark_attendance_as_leave(db, request)
    else:
        balance.pending = float(balance.pending) + days

    approver = db.get(Employee, manager_id) if manager_id else None
    if approver is not None:
        notification_service.notify_employee(
            db,
            approver,
            event=NotificationEvent.LEAVE_APPLIED,
            title="Leave request awaiting your approval",
            message=(
                f"{employee.full_name} applied for {days} day(s) of {leave_type.name} "
                f"from {payload.from_date} to {payload.to_date}."
            ),
            entity_type="leave_request",
            entity_id=request.id,
            action_url=f"/leaves/requests/{request.id}",
        )
    else:
        notification_service.notify_roles(
            db,
            employee.company_id,
            [RoleName.HR, RoleName.COMPANY_ADMIN],
            event=NotificationEvent.LEAVE_APPLIED,
            title="Leave request awaiting approval",
            message=(
                f"{employee.full_name} applied for {days} day(s) of {leave_type.name}. "
                "No reporting manager is assigned."
            ),
            entity_type="leave_request",
            entity_id=request.id,
            action_url=f"/leaves/requests/{request.id}",
        )

    return request


def can_action(principal, request: LeaveRequest) -> bool:
    """HR/admin can action anything in their company; a manager only their reports."""
    from app.core.rbac import P

    if principal.has(P.LEAVE_MANAGE, P.LEAVE_READ_ALL):
        return True
    if not principal.has(P.LEAVE_APPROVE):
        return False
    me = principal.employee
    if me is None:
        return False
    employee = request.employee
    manager_id = employee.employment.manager_id if employee.employment else None
    return manager_id == me.id or request.approver_id == me.id


def approve_leave(db: Session, principal, request: LeaveRequest, comment: str | None) -> LeaveRequest:
    if request.status != LeaveStatus.PENDING:
        raise BadRequest(f"This request is already {request.status.value.lower()}")
    if not can_action(principal, request):
        raise Forbidden("You cannot action this leave request")

    employee = request.employee
    balance = _balance_for(db, employee, request.leave_type_id, request.from_date.year)
    days = float(request.days)

    balance.pending = max(float(balance.pending) - days, 0)
    balance.used = float(balance.used) + days

    request.status = LeaveStatus.APPROVED
    request.actioned_at = utcnow()
    request.actioned_by_user_id = principal.user_id
    request.action_comment = comment

    _mark_attendance_as_leave(db, request)

    notification_service.notify_employee(
        db,
        employee,
        event=NotificationEvent.LEAVE_APPROVED,
        title="Leave approved",
        message=(
            f"Your {request.leave_type.name} from {request.from_date} to {request.to_date} "
            "has been approved."
        ),
        entity_type="leave_request",
        entity_id=request.id,
        action_url=f"/leaves/{request.id}",
    )
    return request


def reject_leave(db: Session, principal, request: LeaveRequest, comment: str) -> LeaveRequest:
    if request.status != LeaveStatus.PENDING:
        raise BadRequest(f"This request is already {request.status.value.lower()}")
    if not can_action(principal, request):
        raise Forbidden("You cannot action this leave request")

    employee = request.employee
    balance = _balance_for(db, employee, request.leave_type_id, request.from_date.year)
    balance.pending = max(float(balance.pending) - float(request.days), 0)

    request.status = LeaveStatus.REJECTED
    request.actioned_at = utcnow()
    request.actioned_by_user_id = principal.user_id
    request.action_comment = comment

    notification_service.notify_employee(
        db,
        employee,
        event=NotificationEvent.LEAVE_REJECTED,
        title="Leave rejected",
        message=(
            f"Your {request.leave_type.name} from {request.from_date} to {request.to_date} "
            f"was rejected. Reason: {comment}"
        ),
        entity_type="leave_request",
        entity_id=request.id,
        action_url=f"/leaves/{request.id}",
    )
    return request


def cancel_leave(db: Session, employee: Employee, request: LeaveRequest) -> LeaveRequest:
    if request.employee_id != employee.id:
        raise Forbidden("You can only cancel your own leave requests")
    if request.status not in (LeaveStatus.PENDING, LeaveStatus.APPROVED):
        raise BadRequest(f"A {request.status.value.lower()} request cannot be cancelled")
    if request.status == LeaveStatus.APPROVED and request.from_date <= today():
        raise BadRequest("An approved leave that has already started cannot be cancelled")

    balance = _balance_for(db, employee, request.leave_type_id, request.from_date.year)
    days = float(request.days)
    if request.status == LeaveStatus.PENDING:
        balance.pending = max(float(balance.pending) - days, 0)
    else:
        balance.used = max(float(balance.used) - days, 0)
        _clear_attendance_leave(db, request)

    request.status = LeaveStatus.CANCELLED
    request.actioned_at = utcnow()

    if request.approver_id:
        notification_service.notify_employee(
            db,
            db.get(Employee, request.approver_id),
            event=NotificationEvent.LEAVE_CANCELLED,
            title="Leave request cancelled",
            message=f"{employee.full_name} cancelled their leave request.",
            entity_type="leave_request",
            entity_id=request.id,
        )
    return request


def file_attachment_as_document(
    db: Session, request: LeaveRequest, file_name: str, mime_type: str | None, size: int
) -> None:
    """Mirrors a leave attachment into the employee's Documents so HR finds it there."""
    from app.models.document import EmployeeDocument
    from app.models.enums import DocumentType

    db.add(
        EmployeeDocument(
            company_id=request.company_id,
            employee_id=request.employee_id,
            document_type=DocumentType.LEAVE_ATTACHMENT,
            title=f"{request.leave_type.name} — {request.from_date:%d %b %Y}",
            description=f"Attached to leave request #{request.id}: {request.reason[:200]}",
            file_name=file_name,
            file_path=request.attachment_path,
            mime_type=mime_type,
            size_bytes=size,
            is_visible_to_employee=True,
            uploaded_by_user_id=request.employee.user_id,
        )
    )
    db.flush()


def edit_leave(db: Session, principal, request: LeaveRequest, payload) -> LeaveRequest:
    """Admin/HR correction of a leave request, re-running the balance arithmetic.

    The old day count is released and the new one re-reserved, so balances stay
    correct whichever direction the edit moves them.
    """
    if request.status == LeaveStatus.CANCELLED:
        raise BadRequest("A cancelled request cannot be edited")

    employee = request.employee
    leave_type = db.get(LeaveType, payload.leave_type_id or request.leave_type_id)
    if leave_type is None or leave_type.company_id != request.company_id:
        raise NotFound("Leave type not found")

    from_date = payload.from_date or request.from_date
    to_date = payload.to_date or request.to_date
    if to_date < from_date:
        raise BadRequest("to_date cannot be before from_date")

    is_half_day = request.is_half_day if payload.is_half_day is None else payload.is_half_day
    if is_half_day and from_date != to_date:
        raise BadRequest("A half-day leave must start and end on the same date")

    if _overlapping(db, employee.id, from_date, to_date, exclude_id=request.id):
        raise Conflict("That range overlaps another leave request for this employee")

    new_days = count_leave_days(db, employee, from_date, to_date, is_half_day)
    if new_days <= 0:
        raise BadRequest("The selected range contains no working days")

    old_days = float(request.days)
    old_balance = _balance_for(db, employee, request.leave_type_id, request.from_date.year)

    # Release what the request currently holds.
    if request.status == LeaveStatus.PENDING:
        old_balance.pending = max(float(old_balance.pending) - old_days, 0)
    elif request.status == LeaveStatus.APPROVED:
        old_balance.used = max(float(old_balance.used) - old_days, 0)
        _clear_attendance_leave(db, request)

    request.leave_type_id = leave_type.id
    request.from_date = from_date
    request.to_date = to_date
    request.is_half_day = is_half_day
    request.half_day_session = payload.half_day_session or request.half_day_session
    request.days = new_days
    if payload.reason:
        request.reason = payload.reason
    request.action_comment = (
        f"Edited by {principal.user.full_name}"
        + (f": {payload.edit_note}" if payload.edit_note else "")
    )

    # Re-reserve against the (possibly different) leave type and year.
    new_balance = _balance_for(db, employee, leave_type.id, from_date.year)
    if request.status == LeaveStatus.PENDING:
        new_balance.pending = float(new_balance.pending) + new_days
    elif request.status == LeaveStatus.APPROVED:
        if leave_type.is_paid and new_days > new_balance.available + new_days - new_days:
            pass  # availability already accounts for the released days
        new_balance.used = float(new_balance.used) + new_days
        db.flush()
        _mark_attendance_as_leave(db, request)

    notification_service.notify_employee(
        db,
        employee,
        event=NotificationEvent.LEAVE_APPLIED,
        title="Leave request updated",
        message=(
            f"HR updated your {leave_type.name}: now {new_days} day(s) "
            f"from {from_date} to {to_date}."
        ),
        entity_type="leave_request",
        entity_id=request.id,
        action_url=f"/leaves/{request.id}",
    )
    db.flush()
    return request


def _leave_dates(db: Session, request: LeaveRequest) -> list[date]:
    employee = request.employee
    policy = get_work_policy(db, employee.company_id, employee)
    holidays = holiday_map(
        db, employee.company_id, request.from_date, request.to_date, employee_location_id(employee)
    )
    return [
        day
        for day in date_range(request.from_date, request.to_date)
        if is_working_day(policy, day) and day not in holidays
    ]


def _mark_attendance_as_leave(db: Session, request: LeaveRequest) -> None:
    """Approved leave writes LEAVE/HALF_DAY rows so payroll and reports agree."""
    status = AttendanceStatus.HALF_DAY if request.is_half_day else AttendanceStatus.LEAVE
    for day in _leave_dates(db, request):
        record = db.scalar(
            select(Attendance).where(
                Attendance.employee_id == request.employee_id, Attendance.date == day
            )
        )
        if record is None:
            db.add(
                Attendance(
                    company_id=request.company_id,
                    employee_id=request.employee_id,
                    date=day,
                    status=status,
                    remarks=f"On {request.leave_type.name}",
                )
            )
        elif record.status in (AttendanceStatus.ABSENT, AttendanceStatus.WEEKEND):
            record.status = status
            record.remarks = f"On {request.leave_type.name}"
    db.flush()


def _clear_attendance_leave(db: Session, request: LeaveRequest) -> None:
    for day in _leave_dates(db, request):
        record = db.scalar(
            select(Attendance).where(
                Attendance.employee_id == request.employee_id, Attendance.date == day
            )
        )
        if record is not None and record.status in (
            AttendanceStatus.LEAVE,
            AttendanceStatus.HALF_DAY,
        ):
            if record.check_in is None:
                db.delete(record)
            else:
                record.status = AttendanceStatus.PRESENT
    db.flush()


def approved_leave_days(
    db: Session, employee_id: int, start: date, end: date
) -> tuple[float, float]:
    """(paid_days, unpaid_days) of approved leave overlapping [start, end]."""
    requests = list(
        db.scalars(
            select(LeaveRequest).where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status == LeaveStatus.APPROVED,
                LeaveRequest.from_date <= end,
                LeaveRequest.to_date >= start,
            )
        )
    )
    paid = unpaid = 0.0
    for req in requests:
        overlap_start = max(req.from_date, start)
        overlap_end = min(req.to_date, end)
        if req.is_half_day:
            days = 0.5 if overlap_start <= req.from_date <= overlap_end else 0.0
        else:
            days = float(len(_leave_dates(db, req)))
            if (req.from_date, req.to_date) != (overlap_start, overlap_end):
                # Partial month overlap: recount only the days inside the window.
                policy = get_work_policy(db, req.company_id, req.employee)
                holidays = holiday_map(
                    db,
                    req.company_id,
                    overlap_start,
                    overlap_end,
                    employee_location_id(req.employee),
                )
                days = float(
                    sum(
                        1
                        for d in date_range(overlap_start, overlap_end)
                        if is_working_day(policy, d) and d not in holidays
                    )
                )
        if req.leave_type.is_paid:
            paid += days
        else:
            unpaid += days
    return paid, unpaid
