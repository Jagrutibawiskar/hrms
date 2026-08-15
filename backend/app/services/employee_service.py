import csv
import io
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequest, Conflict, NotFound
from app.core.security import hash_password
from app.models.employee import (
    Employee,
    EmployeeEmploymentDetail,
    EmployeePersonalDetail,
)
from app.models.enums import EmployeeStatus, NotificationEvent, RoleName
from app.models.organization import Department, Designation, Location
from app.models.policy import LeaveType, WorkPolicy
from app.models.user import User
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeImportRow,
    EmploymentDetailsIn,
    PersonalDetailsIn,
)
from app.services import auth_service, notification_service
from app.services.leave_service import ensure_leave_balances


def next_employee_code(db: Session, company_id: int) -> str:
    """Uses the company's configured format so every creation path agrees."""
    from app.models.company import Company
    from app.services import hr_service

    company = db.get(Company, company_id)
    if company is None:
        raise BadRequest("Company not found")
    return hr_service.generate_employee_code(db, company)


def _validate_org_refs(db: Session, company_id: int, emp: EmploymentDetailsIn) -> None:
    checks = [
        (Department, emp.department_id, "Department"),
        (Designation, emp.designation_id, "Designation"),
        (Location, emp.location_id, "Location"),
        (WorkPolicy, emp.work_policy_id, "Work policy"),
    ]
    for model, value, label in checks:
        if value is None:
            continue
        row = db.get(model, value)
        if row is None or row.company_id != company_id:
            raise BadRequest(f"{label} {value} does not belong to this company")

    if emp.manager_id is not None:
        manager = db.get(Employee, emp.manager_id)
        if manager is None or manager.company_id != company_id:
            raise BadRequest("Manager does not belong to this company")


def create_employee(
    db: Session, company_id: int, payload: EmployeeCreate, created_by_user_id: int | None = None
) -> tuple[Employee, str | None]:
    """Creates the employee, its detail rows, an optional login and leave balances.

    Returns (employee, generated_password | None).
    """
    work_email = str(payload.work_email).strip().lower()

    dupe = db.scalar(
        select(Employee.id).where(
            Employee.company_id == company_id, Employee.work_email == work_email
        )
    )
    if dupe:
        raise Conflict(f"An employee with email {work_email} already exists")

    code = (payload.employee_code or "").strip() or next_employee_code(db, company_id)
    if db.scalar(
        select(Employee.id).where(
            Employee.company_id == company_id, Employee.employee_code == code
        )
    ):
        raise Conflict(f"Employee code {code} is already in use")

    _validate_org_refs(db, company_id, payload.employment)

    generated_password: str | None = None
    user: User | None = None

    if payload.create_login:
        if auth_service.get_user_by_email(db, work_email):
            raise Conflict(f"A user account already exists for {work_email}")
        raw_password = payload.password or secrets.token_urlsafe(9)
        generated_password = None if payload.password else raw_password
        user = User(
            company_id=company_id,
            email=work_email,
            password_hash=hash_password(raw_password),
            first_name=payload.first_name,
            last_name=payload.last_name,
            phone=payload.personal.phone if payload.personal else None,
            is_active=True,
            is_email_verified=True,
        )
        db.add(user)
        db.flush()

    employee = Employee(
        company_id=company_id,
        user_id=user.id if user else None,
        employee_code=code,
        first_name=payload.first_name.strip(),
        last_name=(payload.last_name or "").strip() or None,
        work_email=work_email,
        status=payload.status,
    )
    db.add(employee)
    db.flush()

    if user is not None:
        auth_service.assign_role(db, user, payload.role, company_id)
        if payload.employment.is_manager and payload.role == RoleName.EMPLOYEE:
            auth_service.assign_role(db, user, RoleName.MANAGER, company_id)

    db.add(
        EmployeeEmploymentDetail(
            employee_id=employee.id,
            company_id=company_id,
            **payload.employment.model_dump(),
        )
    )
    personal = payload.personal or PersonalDetailsIn()
    data = personal.model_dump()
    if data.get("personal_email"):
        data["personal_email"] = str(data["personal_email"])
    db.add(EmployeePersonalDetail(employee_id=employee.id, company_id=company_id, **data))

    db.flush()
    ensure_leave_balances(db, employee)

    notification_service.notify_roles(
        db,
        company_id,
        [RoleName.HR, RoleName.COMPANY_ADMIN],
        event=NotificationEvent.EMPLOYEE_ADDED,
        title="New employee added",
        message=f"{employee.full_name} ({code}) has been added to the organization.",
        entity_type="employee",
        entity_id=employee.id,
        action_url=f"/employees/{employee.id}",
    )
    notification_service.audit(
        db,
        company_id=company_id,
        user_id=created_by_user_id,
        action="employee.create",
        entity_type="employee",
        entity_id=employee.id,
        changes={"employee_code": code, "work_email": work_email},
    )

    db.refresh(employee)
    return employee, generated_password


def deactivate_employee(
    db: Session, employee: Employee, exit_date=None, exit_reason=None, status=EmployeeStatus.INACTIVE
) -> Employee:
    employee.status = status
    if employee.employment:
        employee.employment.exit_date = exit_date
        employee.employment.exit_reason = exit_reason
    if employee.user_id:
        user = db.get(User, employee.user_id)
        if user:
            user.is_active = False
    return employee


IMPORT_COLUMNS = list(EmployeeImportRow.model_fields.keys())


def _lookup_id(db: Session, model, company_id: int, name: str | None) -> int | None:
    if not name:
        return None
    row = db.scalar(
        select(model).where(
            model.company_id == company_id, func.lower(model.name) == name.strip().lower()
        )
    )
    if row is None:
        raise BadRequest(f"{model.__name__} '{name}' not found in this company")
    return row.id


def import_employees_csv(
    db: Session, company_id: int, content: bytes, created_by_user_id: int | None = None
) -> dict:
    """Row-per-row import. A bad row is reported and skipped; good rows still commit."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise BadRequest("CSV must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise BadRequest("CSV has no header row")

    missing = {"first_name", "work_email", "joining_date"} - set(reader.fieldnames)
    if missing:
        raise BadRequest(f"CSV is missing required column(s): {', '.join(sorted(missing))}")

    created_ids: list[int] = []
    errors: list[dict] = []

    for index, raw in enumerate(reader, start=2):  # row 1 is the header
        cleaned = {k: (v.strip() if isinstance(v, str) else v) for k, v in raw.items() if k}
        cleaned = {k: (v or None) for k, v in cleaned.items() if k in IMPORT_COLUMNS}
        try:
            row = EmployeeImportRow(**cleaned)
            manager_id = None
            if row.manager_email:
                manager = db.scalar(
                    select(Employee).where(
                        Employee.company_id == company_id,
                        func.lower(Employee.work_email) == row.manager_email.lower(),
                    )
                )
                if manager is None:
                    raise BadRequest(f"Manager '{row.manager_email}' not found")
                manager_id = manager.id

            payload = EmployeeCreate(
                employee_code=row.employee_code,
                first_name=row.first_name,
                last_name=row.last_name,
                work_email=row.work_email,
                employment=EmploymentDetailsIn(
                    department_id=_lookup_id(db, Department, company_id, row.department),
                    designation_id=_lookup_id(db, Designation, company_id, row.designation),
                    location_id=_lookup_id(db, Location, company_id, row.location),
                    manager_id=manager_id,
                    joining_date=row.joining_date,
                    employment_type=row.employment_type,
                ),
                personal=PersonalDetailsIn(
                    phone=row.phone, date_of_birth=row.date_of_birth, gender=row.gender
                ),
                create_login=False,
            )
            with db.begin_nested():
                employee, _ = create_employee(db, company_id, payload, created_by_user_id)
            created_ids.append(employee.id)
        except Exception as exc:  # noqa: BLE001 - surfaced back to the caller per row
            detail = getattr(exc, "detail", None) or str(exc)
            errors.append({"row": index, "error": str(detail)})

    return {
        "created": len(created_ids),
        "failed": len(errors),
        "errors": errors,
        "created_employee_ids": created_ids,
    }


def csv_template() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(IMPORT_COLUMNS)
    writer.writerow(
        [
            "EMP0101",
            "Asha",
            "Verma",
            "asha.verma@example.com",
            "Engineering",
            "Software Engineer",
            "Head Office",
            "",
            "2025-01-06",
            "FULL_TIME",
            "9876543210",
            "1996-04-12",
            "FEMALE",
        ]
    )
    return buffer.getvalue()


def require_employee(db: Session, company_id: int, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None or employee.company_id != company_id:
        raise NotFound("Employee not found")
    return employee


def active_leave_types(db: Session, company_id: int) -> list[LeaveType]:
    return list(
        db.scalars(
            select(LeaveType).where(
                LeaveType.company_id == company_id, LeaveType.is_active.is_(True)
            )
        )
    )
