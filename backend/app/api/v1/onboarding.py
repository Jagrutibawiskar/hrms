from fastapi import APIRouter, File, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.deps import Perm
from app.core.exceptions import BadRequest
from app.core.rbac import P
from app.models.company import Company
from app.models.employee import Employee
from app.models.enums import (
    EmploymentType,
    OnboardingStep,
    RoleName,
)
from app.models.organization import Department, Designation, Location
from app.models.policy import LeaveType
from app.schemas.company import (
    CompanyOut,
    DepartmentCreate,
    DesignationCreate,
    LeaveTypeCreate,
    LocationCreate,
    WorkPolicyIn,
)
from app.schemas.employee import (
    AdminProfileIn,
    EmployeeCreate,
    EmploymentDetailsIn,
    ImportResult,
)
from app.services import company_service, employee_service
from app.utils.dates import today

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

Access = Perm(P.ORG_MANAGE)


class OnboardingStatus(BaseModel):
    current_step: OnboardingStep
    is_onboarded: bool
    steps: list[dict]


class OrganizationStepIn(BaseModel):
    departments: list[DepartmentCreate] = []
    designations: list[DesignationCreate] = []
    locations: list[LocationCreate] = []


class LeavePolicyStepIn(BaseModel):
    """Replaces the seeded defaults when provided; otherwise keeps them."""

    leave_types: list[LeaveTypeCreate] = []


class StepResult(BaseModel):
    message: str
    current_step: OnboardingStep
    is_onboarded: bool
    created: dict = {}


def _company(principal) -> Company:
    return company_service.get_company(principal.db, principal.tenant_id)


def _result(principal, company: Company, message: str, created: dict | None = None) -> StepResult:
    principal.db.commit()
    principal.db.refresh(company)
    return StepResult(
        message=message,
        current_step=company.onboarding_step,
        is_onboarded=company.is_onboarded,
        created=created or {},
    )


@router.get("/status", response_model=OnboardingStatus)
def status_(principal: Access):
    company = _company(principal)
    db = principal.db
    tenant = principal.tenant_id

    def count(model) -> int:
        return db.scalar(select(func.count(model.id)).where(model.company_id == tenant)) or 0

    order = [s for s in OnboardingStep if s != OnboardingStep.COMPLETED]
    current_index = list(OnboardingStep).index(company.onboarding_step)

    steps = []
    for step in order:
        steps.append(
            {
                "step": step.value,
                "completed": list(OnboardingStep).index(step) < current_index
                or company.is_onboarded,
            }
        )

    return OnboardingStatus(
        current_step=company.onboarding_step,
        is_onboarded=company.is_onboarded,
        steps=[
            *steps,
            {"step": "counts", "completed": True, "departments": count(Department),
             "designations": count(Designation), "locations": count(Location),
             "leave_types": count(LeaveType), "employees": count(Employee)},
        ],
    )


@router.get("/company", response_model=CompanyOut)
def get_company_step(principal: Access):
    return _company(principal)


@router.post("/organization", response_model=StepResult, status_code=status.HTTP_201_CREATED)
def organization_step(payload: OrganizationStepIn, principal: Access):
    """Step 2 — bulk-create departments, designations and locations."""
    db, tenant = principal.db, principal.tenant_id
    company = _company(principal)
    created = {"departments": 0, "designations": 0, "locations": 0}

    existing_depts = {
        name.lower(): id_
        for id_, name in db.execute(
            select(Department.id, Department.name).where(Department.company_id == tenant)
        ).all()
    }

    for item in payload.departments:
        key = item.name.strip().lower()
        if key in existing_depts:
            continue
        dept = Department(company_id=tenant, **item.model_dump())
        db.add(dept)
        db.flush()
        existing_depts[key] = dept.id
        created["departments"] += 1

    existing_desig = {
        n.lower()
        for n in db.scalars(select(Designation.name).where(Designation.company_id == tenant))
    }
    for item in payload.designations:
        if item.name.strip().lower() in existing_desig:
            continue
        if item.department_id is not None and item.department_id not in existing_depts.values():
            raise BadRequest(f"Department {item.department_id} does not belong to this company")
        db.add(Designation(company_id=tenant, **item.model_dump()))
        existing_desig.add(item.name.strip().lower())
        created["designations"] += 1

    existing_loc = {
        n.lower() for n in db.scalars(select(Location.name).where(Location.company_id == tenant))
    }
    for item in payload.locations:
        if item.name.strip().lower() in existing_loc:
            continue
        db.add(Location(company_id=tenant, **item.model_dump()))
        existing_loc.add(item.name.strip().lower())
        created["locations"] += 1

    company_service.advance_step(db, company, OnboardingStep.ORGANIZATION)
    return _result(principal, company, "Organization structure saved", created)


@router.post("/work-policy", response_model=StepResult)
def work_policy_step(payload: WorkPolicyIn, principal: Access):
    """Step 3 — working days, hours, break and weekly offs."""
    from app.api.v1.organization import upsert_default_work_policy

    upsert_default_work_policy(payload, principal)
    company = _company(principal)
    company_service.advance_step(principal.db, company, OnboardingStep.WORK_POLICY)
    return _result(principal, company, "Work policy saved")


@router.post("/leave-policy", response_model=StepResult)
def leave_policy_step(payload: LeavePolicyStepIn, principal: Access):
    """Step 4 — override the seeded leave types, or accept them as-is."""
    db, tenant = principal.db, principal.tenant_id
    company = _company(principal)
    created = {"leave_types": 0, "updated": 0}

    existing = {
        lt.code.upper(): lt
        for lt in db.scalars(select(LeaveType).where(LeaveType.company_id == tenant))
    }

    for item in payload.leave_types:
        data = item.model_dump()
        code = data.pop("code").strip().upper()
        current = existing.get(code)
        if current is None:
            db.add(LeaveType(company_id=tenant, code=code, **data))
            created["leave_types"] += 1
        else:
            for field, value in data.items():
                setattr(current, field, value)
            created["updated"] += 1

    company_service.advance_step(db, company, OnboardingStep.LEAVE_POLICY)
    return _result(principal, company, "Leave policy saved", created)


@router.post("/admin", response_model=StepResult)
def admin_profile_step(payload: AdminProfileIn, principal: Access):
    """Step 5 — the admin's own profile, which also creates their employee record."""
    db, tenant = principal.db, principal.tenant_id
    company = _company(principal)
    user = principal.user

    user.first_name = payload.first_name
    user.last_name = payload.last_name
    user.phone = payload.phone

    designation_id = payload.designation_id
    if designation_id is None and payload.designation_name:
        existing = db.scalar(
            select(Designation).where(
                Designation.company_id == tenant,
                func.lower(Designation.name) == payload.designation_name.strip().lower(),
            )
        )
        if existing is None:
            existing = Designation(company_id=tenant, name=payload.designation_name.strip())
            db.add(existing)
            db.flush()
        designation_id = existing.id

    employee = db.scalar(select(Employee).where(Employee.user_id == user.id))
    created = {}

    if employee is None:
        emp_payload = EmployeeCreate(
            first_name=payload.first_name,
            last_name=payload.last_name,
            work_email=user.email,
            employment=EmploymentDetailsIn(
                department_id=payload.department_id,
                designation_id=designation_id,
                location_id=payload.location_id,
                joining_date=payload.joining_date or today(),
                employment_type=EmploymentType.FULL_TIME,
                is_manager=True,
            ),
            create_login=False,
            role=RoleName.COMPANY_ADMIN,
        )
        employee, _ = employee_service.create_employee(db, tenant, emp_payload, user.id)
        employee.user_id = user.id
        db.flush()
        created = {"employee_id": employee.id, "employee_code": employee.employee_code}
    else:
        employee.first_name = payload.first_name
        employee.last_name = payload.last_name
        if employee.employment:
            employee.employment.designation_id = designation_id or employee.employment.designation_id
            employee.employment.department_id = payload.department_id or employee.employment.department_id
            employee.employment.location_id = payload.location_id or employee.employment.location_id
        created = {"employee_id": employee.id}

    company_service.advance_step(db, company, OnboardingStep.ADMIN)
    return _result(principal, company, "Admin profile saved", created)


@router.post("/employees", response_model=StepResult, status_code=status.HTTP_201_CREATED)
def employees_step(payload: list[EmployeeCreate], principal: Access):
    """Step 6 (option A) — add employees one by one."""
    db, tenant = principal.db, principal.tenant_id
    company = _company(principal)
    ids = []
    for item in payload:
        employee, _ = employee_service.create_employee(db, tenant, item, principal.user_id)
        ids.append(employee.id)

    company_service.advance_step(db, company, OnboardingStep.EMPLOYEES)
    return _result(principal, company, f"{len(ids)} employee(s) added", {"employee_ids": ids})


@router.post("/employees/import", response_model=ImportResult)
def import_employees_step(
    principal: Access, file: UploadFile = File(...)
):
    """Step 6 (option B) — bulk import from CSV."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise BadRequest("Please upload a .csv file")

    result = employee_service.import_employees_csv(
        principal.db, principal.tenant_id, file.file.read(), principal.user_id
    )
    company = _company(principal)
    if result["created"]:
        company_service.advance_step(principal.db, company, OnboardingStep.EMPLOYEES)
    principal.db.commit()
    return ImportResult(**result)


@router.post("/skip-employees", response_model=StepResult)
def skip_employees_step(principal: Access):
    """Step 6 (option C) — skip and finish onboarding."""
    company = _company(principal)
    company_service.advance_step(principal.db, company, OnboardingStep.EMPLOYEES)
    return _result(principal, company, "Onboarding complete")


@router.post("/complete", response_model=StepResult)
def complete(principal: Access):
    company = _company(principal)
    company_service.complete_onboarding(principal.db, company)
    return _result(principal, company, "Onboarding complete")


@router.get("/employees/csv-template")
def csv_template(principal: Access):
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(
        employee_service.csv_template(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="employee_import_template.csv"'},
    )
