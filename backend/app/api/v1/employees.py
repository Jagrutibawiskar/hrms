from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased

from app.core.deps import CurrentUser, Perm
from app.core.exceptions import BadRequest, Forbidden
from app.core.pagination import Page, Pagination, build_page, paginate
from app.core.rbac import P
from app.models.employee import Employee, EmployeeEmploymentDetail, EmployeePersonalDetail
from app.models.enums import EmployeeStatus
from app.models.user import User
from app.schemas.common import Message
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeDeactivate,
    EmployeeListItem,
    EmployeeOut,
    EmployeeUpdate,
    EmploymentDetailsOut,
    ImportResult,
    PersonalDetailsOut,
)
from app.services import employee_service, notification_service

router = APIRouter(prefix="/employees", tags=["Employees"])

ReadAccess = Perm(
    P.EMPLOYEE_READ_ALL, P.EMPLOYEE_READ_TEAM, P.EMPLOYEE_READ_SELF
)
WriteAccess = Perm(P.EMPLOYEE_CREATE)
UpdateAccess = Perm(P.EMPLOYEE_UPDATE)


class CreatedEmployee(BaseModel):
    employee: EmployeeOut
    generated_password: str | None = None


def serialize_employee(db, employee: Employee) -> EmployeeOut:
    emp = employee.employment
    employment = None
    if emp is not None:
        manager = db.get(Employee, emp.manager_id) if emp.manager_id else None
        employment = EmploymentDetailsOut(
            department_id=emp.department_id,
            department_name=emp.department.name if emp.department else None,
            designation_id=emp.designation_id,
            designation_name=emp.designation.name if emp.designation else None,
            location_id=emp.location_id,
            location_name=emp.location.name if emp.location else None,
            manager_id=emp.manager_id,
            manager_name=manager.full_name if manager else None,
            work_policy_id=emp.work_policy_id,
            joining_date=emp.joining_date,
            confirmation_date=emp.confirmation_date,
            probation_months=emp.probation_months,
            employment_type=emp.employment_type,
            is_manager=emp.is_manager,
            exit_date=emp.exit_date,
            exit_reason=emp.exit_reason,
        )

    roles: list[str] = []
    if employee.user_id:
        user = db.get(User, employee.user_id)
        roles = user.role_names if user else []

    return EmployeeOut(
        id=employee.id,
        company_id=employee.company_id,
        user_id=employee.user_id,
        employee_code=employee.employee_code,
        first_name=employee.first_name,
        last_name=employee.last_name,
        full_name=employee.full_name,
        work_email=employee.work_email,
        profile_photo_path=employee.profile_photo_path,
        status=employee.status,
        roles=roles,
        personal=PersonalDetailsOut.model_validate(employee.personal)
        if employee.personal
        else None,
        employment=employment,
        created_at=employee.created_at,
    )


def visible_employee_ids(principal) -> list[int] | None:
    """None means "all employees in the tenant"; a list narrows to the caller's scope."""
    if principal.has(P.EMPLOYEE_READ_ALL):
        return None
    if principal.has(P.EMPLOYEE_READ_TEAM):
        return principal.team_employee_ids()
    me = principal.employee
    return [me.id] if me else []


def require_visible(principal, employee_id: int) -> Employee:
    employee = employee_service.require_employee(principal.db, principal.tenant_id, employee_id)
    allowed = visible_employee_ids(principal)
    if allowed is not None and employee.id not in allowed:
        raise Forbidden("You do not have access to this employee record")
    return employee


@router.get("", response_model=Page[EmployeeListItem])
def list_employees(
    pagination: Pagination,
    principal: ReadAccess,
    search: Annotated[str | None, Query(description="Name, code or email")] = None,
    department_id: int | None = None,
    designation_id: int | None = None,
    location_id: int | None = None,
    manager_id: int | None = None,
    status_: Annotated[EmployeeStatus | None, Query(alias="status")] = None,
):
    db = principal.db
    detail = aliased(EmployeeEmploymentDetail)

    stmt = (
        select(Employee)
        .join(detail, detail.employee_id == Employee.id, isouter=True)
        .where(Employee.company_id == principal.tenant_id)
    )

    allowed = visible_employee_ids(principal)
    if allowed is not None:
        stmt = stmt.where(Employee.id.in_(allowed or [-1]))

    if search:
        pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Employee.first_name).like(pattern),
                func.lower(Employee.last_name).like(pattern),
                func.lower(Employee.work_email).like(pattern),
                func.lower(Employee.employee_code).like(pattern),
            )
        )
    if department_id:
        stmt = stmt.where(detail.department_id == department_id)
    if designation_id:
        stmt = stmt.where(detail.designation_id == designation_id)
    if location_id:
        stmt = stmt.where(detail.location_id == location_id)
    if manager_id:
        stmt = stmt.where(detail.manager_id == manager_id)
    if status_:
        stmt = stmt.where(Employee.status == status_)

    stmt = stmt.order_by(Employee.employee_code)
    rows, total = paginate(db, stmt, pagination)

    items = []
    for employee in rows:
        emp = employee.employment
        manager = db.get(Employee, emp.manager_id) if emp and emp.manager_id else None
        items.append(
            EmployeeListItem(
                id=employee.id,
                employee_code=employee.employee_code,
                full_name=employee.full_name,
                work_email=employee.work_email,
                department_name=emp.department.name if emp and emp.department else None,
                designation_name=emp.designation.name if emp and emp.designation else None,
                manager_name=manager.full_name if manager else None,
                location_name=emp.location.name if emp and emp.location else None,
                joining_date=emp.joining_date if emp else None,
                employment_type=emp.employment_type.value if emp else None,
                status=employee.status,
            )
        )
    return build_page(items, total, pagination)


@router.post("", response_model=CreatedEmployee, status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeCreate, principal: WriteAccess):
    employee, generated = employee_service.create_employee(
        principal.db, principal.tenant_id, payload, principal.user_id
    )
    principal.db.commit()
    principal.db.refresh(employee)
    return CreatedEmployee(
        employee=serialize_employee(principal.db, employee), generated_password=generated
    )


@router.get("/me", response_model=EmployeeOut)
def my_profile(principal: CurrentUser):
    return serialize_employee(principal.db, principal.employee_or_404)


@router.get("/csv-template", response_class=PlainTextResponse)
def download_csv_template(principal: WriteAccess):
    return PlainTextResponse(
        employee_service.csv_template(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="employee_import_template.csv"'},
    )


@router.post("/import", response_model=ImportResult)
def import_employees(
    principal: WriteAccess, file: UploadFile = File(...)
):
    if not (file.filename or "").lower().endswith(".csv"):
        raise BadRequest("Please upload a .csv file")
    result = employee_service.import_employees_csv(
        principal.db, principal.tenant_id, file.file.read(), principal.user_id
    )
    principal.db.commit()
    return ImportResult(**result)


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, principal: ReadAccess):
    return serialize_employee(principal.db, require_visible(principal, employee_id))


@router.patch("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: int, payload: EmployeeUpdate, principal: UpdateAccess
):
    db = principal.db
    employee = employee_service.require_employee(db, principal.tenant_id, employee_id)

    core = payload.model_dump(exclude_unset=True, exclude={"employment", "personal"})
    if "work_email" in core and core["work_email"]:
        core["work_email"] = str(core["work_email"]).lower()
        clash = db.scalar(
            select(Employee.id).where(
                Employee.company_id == principal.tenant_id,
                Employee.work_email == core["work_email"],
                Employee.id != employee.id,
            )
        )
        if clash:
            raise BadRequest("Another employee already uses this work email")
    for field, value in core.items():
        setattr(employee, field, value)

    if payload.employment is not None:
        detail = employee.employment
        if detail is None:
            detail = EmployeeEmploymentDetail(
                employee_id=employee.id, company_id=principal.tenant_id,
                joining_date=payload.employment.joining_date,
            )
            db.add(detail)
        if payload.employment.manager_id == employee.id:
            raise BadRequest("An employee cannot be their own manager")
        for field, value in payload.employment.model_dump(exclude_unset=True).items():
            setattr(detail, field, value)

    if payload.personal is not None:
        detail = employee.personal
        if detail is None:
            detail = EmployeePersonalDetail(
                employee_id=employee.id, company_id=principal.tenant_id
            )
            db.add(detail)
        for field, value in payload.personal.model_dump(exclude_unset=True).items():
            setattr(detail, field, str(value) if field == "personal_email" and value else value)

    notification_service.audit(
        db,
        company_id=principal.tenant_id,
        user_id=principal.user_id,
        action="employee.update",
        entity_type="employee",
        entity_id=employee.id,
        changes=payload.model_dump(exclude_unset=True, mode="json"),
    )
    db.commit()
    db.refresh(employee)
    return serialize_employee(db, employee)


@router.post("/{employee_id}/deactivate", response_model=EmployeeOut)
def deactivate_employee(
    employee_id: int,
    payload: EmployeeDeactivate,
    principal: Perm(P.EMPLOYEE_DEACTIVATE),
):
    db = principal.db
    employee = employee_service.require_employee(db, principal.tenant_id, employee_id)
    if employee.user_id == principal.user_id:
        raise BadRequest("You cannot deactivate your own account")

    reports = db.scalar(
        select(func.count(EmployeeEmploymentDetail.id)).where(
            EmployeeEmploymentDetail.manager_id == employee.id
        )
    )
    if reports:
        raise BadRequest(
            f"This employee manages {reports} person(s). Reassign them before deactivating."
        )

    employee_service.deactivate_employee(
        db, employee, payload.exit_date, payload.exit_reason, payload.status
    )
    notification_service.audit(
        db,
        company_id=principal.tenant_id,
        user_id=principal.user_id,
        action="employee.deactivate",
        entity_type="employee",
        entity_id=employee.id,
        changes={"status": payload.status.value, "exit_date": str(payload.exit_date)},
    )
    db.commit()
    db.refresh(employee)
    return serialize_employee(db, employee)


@router.post("/{employee_id}/activate", response_model=EmployeeOut)
def activate_employee(
    employee_id: int, principal: Perm(P.EMPLOYEE_UPDATE)
):
    db = principal.db
    employee = employee_service.require_employee(db, principal.tenant_id, employee_id)
    employee.status = EmployeeStatus.ACTIVE
    if employee.employment:
        employee.employment.exit_date = None
        employee.employment.exit_reason = None
    if employee.user_id:
        user = db.get(User, employee.user_id)
        if user:
            user.is_active = True
    db.commit()
    db.refresh(employee)
    return serialize_employee(db, employee)


@router.get("/{employee_id}/team", response_model=list[EmployeeListItem])
def direct_reports(employee_id: int, principal: ReadAccess):
    require_visible(principal, employee_id)
    db = principal.db
    reports = list(
        db.scalars(
            select(Employee)
            .join(EmployeeEmploymentDetail, EmployeeEmploymentDetail.employee_id == Employee.id)
            .where(
                Employee.company_id == principal.tenant_id,
                EmployeeEmploymentDetail.manager_id == employee_id,
            )
            .order_by(Employee.employee_code)
        )
    )
    return [
        EmployeeListItem(
            id=e.id,
            employee_code=e.employee_code,
            full_name=e.full_name,
            work_email=e.work_email,
            department_name=e.employment.department.name
            if e.employment and e.employment.department
            else None,
            designation_name=e.employment.designation.name
            if e.employment and e.employment.designation
            else None,
            joining_date=e.employment.joining_date if e.employment else None,
            employment_type=e.employment.employment_type.value if e.employment else None,
            status=e.status,
        )
        for e in reports
    ]


@router.delete("/{employee_id}", response_model=Message)
def delete_employee(
    employee_id: int, principal: Perm(P.EMPLOYEE_DEACTIVATE)
):
    """Hard delete. Only allowed while the record has no history attached."""
    from app.models.attendance import Attendance
    from app.models.leave import LeaveRequest
    from app.models.payroll import PayrollItem

    db = principal.db
    employee = employee_service.require_employee(db, principal.tenant_id, employee_id)

    for model, label in ((Attendance, "attendance"), (LeaveRequest, "leave"), (PayrollItem, "payroll")):
        if db.scalar(select(func.count(model.id)).where(model.employee_id == employee.id)):
            raise BadRequest(
                f"This employee has {label} records. Deactivate the employee instead of deleting."
            )

    db.delete(employee)
    db.commit()
    return Message(message="Employee deleted")
