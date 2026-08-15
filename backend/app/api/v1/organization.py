from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.core.deps import Perm
from app.core.exceptions import BadRequest, Conflict, NotFound
from app.core.rbac import P
from app.models.employee import EmployeeEmploymentDetail
from app.models.organization import Department, Designation, Location
from app.models.policy import LeaveType, WorkPolicy
from app.schemas.common import Message
from app.schemas.company import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    DesignationCreate,
    DesignationOut,
    DesignationUpdate,
    LeaveTypeCreate,
    LeaveTypeOut,
    LeaveTypeUpdate,
    LocationCreate,
    LocationOut,
    LocationUpdate,
    WorkPolicyIn,
    WorkPolicyOut,
)

router = APIRouter(prefix="/organization", tags=["Organization"])

ReadAccess = Perm(P.ORG_READ)
ManageAccess = Perm(P.ORG_MANAGE)


def _scoped(db, model, company_id: int, obj_id: int):
    obj = db.get(model, obj_id)
    if obj is None or obj.company_id != company_id:
        raise NotFound(f"{model.__name__} not found")
    return obj


# ------------------------------------------------------------------ departments


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    principal: ReadAccess,
    include_inactive: bool = Query(False),
):
    stmt = select(Department).where(Department.company_id == principal.tenant_id)
    if not include_inactive:
        stmt = stmt.where(Department.is_active.is_(True))

    departments = list(principal.db.scalars(stmt.order_by(Department.name)))
    counts = dict(
        principal.db.execute(
            select(
                EmployeeEmploymentDetail.department_id,
                func.count(EmployeeEmploymentDetail.id),
            )
            .where(EmployeeEmploymentDetail.company_id == principal.tenant_id)
            .group_by(EmployeeEmploymentDetail.department_id)
        ).all()
    )
    return [
        DepartmentOut(
            id=d.id,
            name=d.name,
            code=d.code,
            description=d.description,
            head_employee_id=d.head_employee_id,
            is_active=d.is_active,
            employee_count=counts.get(d.id, 0),
        )
        for d in departments
    ]


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreate, principal: ManageAccess):
    exists = principal.db.scalar(
        select(Department).where(
            Department.company_id == principal.tenant_id,
            func.lower(Department.name) == payload.name.strip().lower(),
        )
    )
    if exists:
        raise Conflict(f"Department '{payload.name}' already exists")

    dept = Department(company_id=principal.tenant_id, **payload.model_dump())
    principal.db.add(dept)
    principal.db.commit()
    principal.db.refresh(dept)
    return DepartmentOut.model_validate(dept, from_attributes=True)


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: int, payload: DepartmentUpdate, principal: ManageAccess
):
    dept = _scoped(principal.db, Department, principal.tenant_id, department_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(dept, field, value)
    principal.db.commit()
    principal.db.refresh(dept)
    return DepartmentOut.model_validate(dept, from_attributes=True)


@router.delete("/departments/{department_id}", response_model=Message)
def delete_department(department_id: int, principal: ManageAccess):
    dept = _scoped(principal.db, Department, principal.tenant_id, department_id)
    in_use = principal.db.scalar(
        select(func.count(EmployeeEmploymentDetail.id)).where(
            EmployeeEmploymentDetail.department_id == department_id
        )
    )
    if in_use:
        # Keep referential history intact — deactivate instead of deleting.
        dept.is_active = False
        principal.db.commit()
        return Message(message=f"Department has {in_use} employee(s); deactivated instead")

    principal.db.delete(dept)
    principal.db.commit()
    return Message(message="Department deleted")


# ------------------------------------------------------------------ designations


@router.get("/designations", response_model=list[DesignationOut])
def list_designations(principal: ReadAccess, include_inactive: bool = Query(False)):
    stmt = select(Designation).where(Designation.company_id == principal.tenant_id)
    if not include_inactive:
        stmt = stmt.where(Designation.is_active.is_(True))
    return list(principal.db.scalars(stmt.order_by(Designation.name)))


@router.post("/designations", response_model=DesignationOut, status_code=status.HTTP_201_CREATED)
def create_designation(payload: DesignationCreate, principal: ManageAccess):
    if principal.db.scalar(
        select(Designation).where(
            Designation.company_id == principal.tenant_id,
            func.lower(Designation.name) == payload.name.strip().lower(),
        )
    ):
        raise Conflict(f"Designation '{payload.name}' already exists")
    if payload.department_id:
        _scoped(principal.db, Department, principal.tenant_id, payload.department_id)

    row = Designation(company_id=principal.tenant_id, **payload.model_dump())
    principal.db.add(row)
    principal.db.commit()
    principal.db.refresh(row)
    return row


@router.patch("/designations/{designation_id}", response_model=DesignationOut)
def update_designation(
    designation_id: int, payload: DesignationUpdate, principal: ManageAccess
):
    row = _scoped(principal.db, Designation, principal.tenant_id, designation_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    principal.db.commit()
    principal.db.refresh(row)
    return row


@router.delete("/designations/{designation_id}", response_model=Message)
def delete_designation(designation_id: int, principal: ManageAccess):
    row = _scoped(principal.db, Designation, principal.tenant_id, designation_id)
    in_use = principal.db.scalar(
        select(func.count(EmployeeEmploymentDetail.id)).where(
            EmployeeEmploymentDetail.designation_id == designation_id
        )
    )
    if in_use:
        row.is_active = False
        principal.db.commit()
        return Message(message=f"Designation has {in_use} employee(s); deactivated instead")
    principal.db.delete(row)
    principal.db.commit()
    return Message(message="Designation deleted")


# ------------------------------------------------------------------ locations


@router.get("/locations", response_model=list[LocationOut])
def list_locations(principal: ReadAccess, include_inactive: bool = Query(False)):
    stmt = select(Location).where(Location.company_id == principal.tenant_id)
    if not include_inactive:
        stmt = stmt.where(Location.is_active.is_(True))
    return list(principal.db.scalars(stmt.order_by(Location.name)))


@router.post("/locations", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
def create_location(payload: LocationCreate, principal: ManageAccess):
    if principal.db.scalar(
        select(Location).where(
            Location.company_id == principal.tenant_id,
            func.lower(Location.name) == payload.name.strip().lower(),
        )
    ):
        raise Conflict(f"Location '{payload.name}' already exists")
    row = Location(company_id=principal.tenant_id, **payload.model_dump())
    principal.db.add(row)
    principal.db.commit()
    principal.db.refresh(row)
    return row


@router.patch("/locations/{location_id}", response_model=LocationOut)
def update_location(
    location_id: int, payload: LocationUpdate, principal: ManageAccess
):
    row = _scoped(principal.db, Location, principal.tenant_id, location_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    principal.db.commit()
    principal.db.refresh(row)
    return row


@router.delete("/locations/{location_id}", response_model=Message)
def delete_location(location_id: int, principal: ManageAccess):
    row = _scoped(principal.db, Location, principal.tenant_id, location_id)
    in_use = principal.db.scalar(
        select(func.count(EmployeeEmploymentDetail.id)).where(
            EmployeeEmploymentDetail.location_id == location_id
        )
    )
    if in_use:
        row.is_active = False
        principal.db.commit()
        return Message(message=f"Location has {in_use} employee(s); deactivated instead")
    principal.db.delete(row)
    principal.db.commit()
    return Message(message="Location deleted")


# ------------------------------------------------------------------ work policy


@router.get("/work-policies", response_model=list[WorkPolicyOut])
def list_work_policies(principal: ReadAccess):
    rows = principal.db.scalars(
        select(WorkPolicy)
        .where(WorkPolicy.company_id == principal.tenant_id)
        .order_by(WorkPolicy.is_default.desc(), WorkPolicy.id)
    )
    return [_policy_out(p) for p in rows]


def _policy_out(policy: WorkPolicy) -> WorkPolicyOut:
    return WorkPolicyOut(
        id=policy.id,
        name=policy.name,
        working_days=policy.working_days,
        weekly_off_days=policy.weekly_off_days,
        start_time=policy.start_time,
        end_time=policy.end_time,
        break_start=policy.break_start,
        break_end=policy.break_end,
        full_day_hours=float(policy.full_day_hours),
        half_day_hours=float(policy.half_day_hours),
        late_grace_minutes=policy.late_grace_minutes,
        is_default=policy.is_default,
        is_active=policy.is_active,
    )


@router.put("/work-policies/default", response_model=WorkPolicyOut)
def upsert_default_work_policy(payload: WorkPolicyIn, principal: ManageAccess):
    """Creates or replaces the company's default work policy."""
    policy = principal.db.scalar(
        select(WorkPolicy).where(
            WorkPolicy.company_id == principal.tenant_id, WorkPolicy.is_default.is_(True)
        )
    )
    if policy is None:
        policy = WorkPolicy(company_id=principal.tenant_id, is_default=True)
        principal.db.add(policy)

    for field, value in payload.model_dump().items():
        setattr(policy, field, value)
    policy.is_active = True

    principal.db.commit()
    principal.db.refresh(policy)
    return _policy_out(policy)


# ------------------------------------------------------------------ leave types


@router.get("/leave-types", response_model=list[LeaveTypeOut])
def list_leave_types(principal: ReadAccess, include_inactive: bool = Query(False)):
    stmt = select(LeaveType).where(LeaveType.company_id == principal.tenant_id)
    if not include_inactive:
        stmt = stmt.where(LeaveType.is_active.is_(True))
    return list(principal.db.scalars(stmt.order_by(LeaveType.id)))


@router.post("/leave-types", response_model=LeaveTypeOut, status_code=status.HTTP_201_CREATED)
def create_leave_type(payload: LeaveTypeCreate, principal: ManageAccess):
    if principal.db.scalar(
        select(LeaveType).where(
            LeaveType.company_id == principal.tenant_id,
            func.upper(LeaveType.code) == payload.code.strip().upper(),
        )
    ):
        raise Conflict(f"Leave type code '{payload.code}' already exists")
    if payload.carry_forward and payload.max_carry_forward <= 0:
        raise BadRequest("max_carry_forward must be greater than 0 when carry_forward is enabled")

    data = payload.model_dump()
    data["code"] = data["code"].strip().upper()
    row = LeaveType(company_id=principal.tenant_id, **data)
    principal.db.add(row)
    principal.db.commit()
    principal.db.refresh(row)
    return row


@router.patch("/leave-types/{leave_type_id}", response_model=LeaveTypeOut)
def update_leave_type(
    leave_type_id: int, payload: LeaveTypeUpdate, principal: ManageAccess
):
    row = _scoped(principal.db, LeaveType, principal.tenant_id, leave_type_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    principal.db.commit()
    principal.db.refresh(row)
    return row
