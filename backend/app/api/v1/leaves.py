from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from sqlalchemy import select

from app.core.deps import Perm
from app.core.exceptions import Forbidden, NotFound
from app.core.pagination import Page, Pagination, build_page, paginate
from app.core.rbac import P
from app.models.employee import EmployeeEmploymentDetail
from app.models.enums import HalfDaySession, LeaveStatus
from app.models.leave import LeaveRequest
from app.models.policy import LeaveBalance
from app.schemas.leave import (
    LeaveAction,
    LeaveApply,
    LeaveBalanceAdjust,
    LeaveBalanceOut,
    LeaveEdit,
    LeaveRejectAction,
    LeaveRequestOut,
)
from app.services import employee_service, leave_service
from app.utils.files import save_upload

router = APIRouter(prefix="/leaves", tags=["Leave"])

SelfAccess = Perm(P.LEAVE_APPLY, P.LEAVE_READ_SELF)
ReadAccess = Perm(P.LEAVE_READ_ALL, P.LEAVE_READ_TEAM, P.LEAVE_READ_SELF)
ApproveAccess = Perm(P.LEAVE_APPROVE, P.LEAVE_MANAGE)
ManageAccess = Perm(P.LEAVE_MANAGE)


def to_out(request: LeaveRequest) -> LeaveRequestOut:
    return LeaveRequestOut(
        id=request.id,
        employee_id=request.employee_id,
        employee_name=request.employee.full_name if request.employee else None,
        employee_code=request.employee.employee_code if request.employee else None,
        leave_type_id=request.leave_type_id,
        leave_type_name=request.leave_type.name if request.leave_type else None,
        from_date=request.from_date,
        to_date=request.to_date,
        is_half_day=request.is_half_day,
        half_day_session=request.half_day_session,
        days=float(request.days),
        reason=request.reason,
        attachment_path=request.attachment_path,
        status=request.status,
        applied_at=request.applied_at,
        approver_id=request.approver_id,
        approver_name=request.approver.full_name if request.approver else None,
        actioned_at=request.actioned_at,
        action_comment=request.action_comment,
    )


def balance_out(balance: LeaveBalance) -> LeaveBalanceOut:
    return LeaveBalanceOut(
        leave_type_id=balance.leave_type_id,
        leave_type_name=balance.leave_type.name,
        leave_type_code=balance.leave_type.code,
        is_paid=balance.leave_type.is_paid,
        year=balance.year,
        allocated=float(balance.allocated),
        carried_forward=float(balance.carried_forward),
        used=float(balance.used),
        pending=float(balance.pending),
        available=balance.available,
        total=balance.total,
    )


def _scope_ids(principal) -> list[int] | None:
    if principal.has(P.LEAVE_READ_ALL, P.LEAVE_MANAGE):
        return None
    if principal.has(P.LEAVE_READ_TEAM):
        return principal.team_employee_ids()
    me = principal.employee
    return [me.id] if me else []


def _require_request(principal, request_id: int) -> LeaveRequest:
    request = principal.db.get(LeaveRequest, request_id)
    if request is None or request.company_id != principal.tenant_id:
        raise NotFound("Leave request not found")
    return request


# ------------------------------------------------------------------ employee


@router.get("/balances", response_model=list[LeaveBalanceOut])
def my_balances(principal: SelfAccess, year: int | None = None):
    balances = leave_service.get_balances(principal.db, principal.employee_or_404, year)
    principal.db.commit()
    return [balance_out(b) for b in balances]


@router.get("/me", response_model=Page[LeaveRequestOut])
def my_leaves(
    pagination: Pagination,
    principal: SelfAccess,
    status_: Annotated[LeaveStatus | None, Query(alias="status")] = None,
):
    employee = principal.employee_or_404
    stmt = select(LeaveRequest).where(LeaveRequest.employee_id == employee.id)
    if status_:
        stmt = stmt.where(LeaveRequest.status == status_)
    stmt = stmt.order_by(LeaveRequest.applied_at.desc())
    rows, total = paginate(principal.db, stmt, pagination)
    return build_page([to_out(r) for r in rows], total, pagination)


@router.post("", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
def apply_leave(payload: LeaveApply, principal: SelfAccess):
    request = leave_service.apply_leave(principal.db, principal.employee_or_404, payload)
    principal.db.commit()
    principal.db.refresh(request)
    return to_out(request)


@router.post(
    "/with-attachment", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED
)
def apply_leave_with_attachment(
    principal: SelfAccess,
    leave_type_id: int = Form(...),
    from_date: date = Form(...),
    to_date: date = Form(...),
    reason: str = Form(...),
    is_half_day: bool = Form(False),
    half_day_session: HalfDaySession | None = Form(None),
    file: UploadFile | None = File(None),
):
    """Same as POST /leaves but multipart, for leave types requiring a document."""
    employee = principal.employee_or_404
    attachment, size = None, 0
    if file is not None:
        attachment, size = save_upload(file, f"company_{principal.tenant_id}/leave")

    payload = LeaveApply(
        leave_type_id=leave_type_id,
        from_date=from_date,
        to_date=to_date,
        reason=reason,
        is_half_day=is_half_day,
        half_day_session=half_day_session,
    )
    request = leave_service.apply_leave(principal.db, employee, payload, attachment)

    # The proof the employee attached should also live in their Documents.
    if attachment:
        leave_service.file_attachment_as_document(
            principal.db, request, file.filename or "attachment", file.content_type, size
        )

    principal.db.commit()
    principal.db.refresh(request)
    return to_out(request)


@router.patch("/{request_id}", response_model=LeaveRequestOut)
def edit_leave(request_id: int, payload: LeaveEdit, principal: ManageAccess):
    """Admin/HR correction of any leave request. Balances are recalculated."""
    request = _require_request(principal, request_id)
    leave_service.edit_leave(principal.db, principal, request, payload)
    principal.db.commit()
    principal.db.refresh(request)
    return to_out(request)


@router.post("/{request_id}/cancel", response_model=LeaveRequestOut)
def cancel_leave(request_id: int, principal: SelfAccess):
    request = _require_request(principal, request_id)
    leave_service.cancel_leave(principal.db, principal.employee_or_404, request)
    principal.db.commit()
    principal.db.refresh(request)
    return to_out(request)


# ------------------------------------------------------------------ manager / HR


@router.get("/requests", response_model=Page[LeaveRequestOut])
def list_requests(
    pagination: Pagination,
    principal: ReadAccess,
    status_: Annotated[LeaveStatus | None, Query(alias="status")] = None,
    employee_id: int | None = None,
    department_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
):
    stmt = select(LeaveRequest).where(LeaveRequest.company_id == principal.tenant_id)

    allowed = _scope_ids(principal)
    if allowed is not None:
        stmt = stmt.where(LeaveRequest.employee_id.in_(allowed or [-1]))
    if employee_id:
        if allowed is not None and employee_id not in allowed:
            raise Forbidden("You do not have access to this employee's leave")
        stmt = stmt.where(LeaveRequest.employee_id == employee_id)
    if department_id:
        stmt = stmt.where(
            LeaveRequest.employee_id.in_(
                select(EmployeeEmploymentDetail.employee_id).where(
                    EmployeeEmploymentDetail.department_id == department_id
                )
            )
        )
    if status_:
        stmt = stmt.where(LeaveRequest.status == status_)
    if from_date:
        stmt = stmt.where(LeaveRequest.to_date >= from_date)
    if to_date:
        stmt = stmt.where(LeaveRequest.from_date <= to_date)

    stmt = stmt.order_by(LeaveRequest.applied_at.desc())
    rows, total = paginate(principal.db, stmt, pagination)
    return build_page([to_out(r) for r in rows], total, pagination)


@router.get("/requests/pending", response_model=list[LeaveRequestOut])
def pending_for_me(principal: ApproveAccess):
    """Requests this user is expected to action."""
    me = principal.employee
    stmt = select(LeaveRequest).where(
        LeaveRequest.company_id == principal.tenant_id,
        LeaveRequest.status == LeaveStatus.PENDING,
    )
    if not principal.has(P.LEAVE_MANAGE, P.LEAVE_READ_ALL):
        if me is None:
            return []
        stmt = stmt.where(LeaveRequest.approver_id == me.id)
    return [to_out(r) for r in principal.db.scalars(stmt.order_by(LeaveRequest.applied_at))]


@router.get("/{request_id}", response_model=LeaveRequestOut)
def get_request(request_id: int, principal: ReadAccess):
    request = _require_request(principal, request_id)
    allowed = _scope_ids(principal)
    if allowed is not None and request.employee_id not in allowed:
        raise Forbidden("You do not have access to this leave request")
    return to_out(request)


@router.post("/{request_id}/approve", response_model=LeaveRequestOut)
def approve(request_id: int, payload: LeaveAction, principal: ApproveAccess):
    request = _require_request(principal, request_id)
    leave_service.approve_leave(principal.db, principal, request, payload.comment)
    principal.db.commit()
    principal.db.refresh(request)
    return to_out(request)


@router.post("/{request_id}/reject", response_model=LeaveRequestOut)
def reject(request_id: int, payload: LeaveRejectAction, principal: ApproveAccess):
    request = _require_request(principal, request_id)
    leave_service.reject_leave(principal.db, principal, request, payload.comment)
    principal.db.commit()
    principal.db.refresh(request)
    return to_out(request)


@router.get("/balances/{employee_id}", response_model=list[LeaveBalanceOut])
def employee_balances(
    employee_id: int, principal: ReadAccess, year: int | None = None
):
    allowed = _scope_ids(principal)
    if allowed is not None and employee_id not in allowed:
        raise Forbidden("You do not have access to this employee's leave balance")
    employee = employee_service.require_employee(principal.db, principal.tenant_id, employee_id)
    balances = leave_service.get_balances(principal.db, employee, year)
    principal.db.commit()
    return [balance_out(b) for b in balances]


@router.put("/balances", response_model=LeaveBalanceOut)
def adjust_balance(payload: LeaveBalanceAdjust, principal: ManageAccess):
    """HR override of an employee's allocation for a leave type and year."""
    employee = employee_service.require_employee(
        principal.db, principal.tenant_id, payload.employee_id
    )
    leave_service.ensure_leave_balances(principal.db, employee, payload.year)
    balance = principal.db.scalar(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == employee.id,
            LeaveBalance.leave_type_id == payload.leave_type_id,
            LeaveBalance.year == payload.year,
        )
    )
    if balance is None:
        raise NotFound("Leave balance not found for that leave type")

    balance.allocated = payload.allocated
    balance.carried_forward = payload.carried_forward
    principal.db.commit()
    principal.db.refresh(balance)
    return balance_out(balance)
