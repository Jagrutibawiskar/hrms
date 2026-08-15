from datetime import date

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.deps import Perm
from app.core.exceptions import Conflict, NotFound
from app.core.rbac import P
from app.models.organization import Location
from app.models.policy import Holiday
from app.schemas.common import Message
from app.schemas.company import HolidayCreate, HolidayOut, HolidayUpdate
from app.utils.dates import today

router = APIRouter(prefix="/holidays", tags=["Holidays"])

ReadAccess = Perm(P.HOLIDAY_READ)
ManageAccess = Perm(P.HOLIDAY_MANAGE)


@router.get("", response_model=list[HolidayOut])
def list_holidays(
    principal: ReadAccess,
    year: int | None = None,
    location_id: int | None = None,
):
    target_year = year or today().year
    stmt = select(Holiday).where(
        Holiday.company_id == principal.tenant_id,
        Holiday.date >= date(target_year, 1, 1),
        Holiday.date <= date(target_year, 12, 31),
    )
    rows = list(principal.db.scalars(stmt.order_by(Holiday.date)))
    if location_id is not None:
        rows = [h for h in rows if h.location_id in (None, location_id)]
    return rows


@router.get("/upcoming", response_model=list[HolidayOut])
def upcoming_holidays(principal: ReadAccess, limit: int = 5):
    """Next holidays for the caller's own location (plus company-wide ones)."""
    employee = principal.employee
    location_id = (
        employee.employment.location_id if employee and employee.employment else None
    )
    rows = list(
        principal.db.scalars(
            select(Holiday)
            .where(Holiday.company_id == principal.tenant_id, Holiday.date >= today())
            .order_by(Holiday.date)
        )
    )
    filtered = [h for h in rows if h.location_id is None or h.location_id == location_id]
    return filtered[:limit]


@router.post("", response_model=HolidayOut, status_code=status.HTTP_201_CREATED)
def create_holiday(payload: HolidayCreate, principal: ManageAccess):
    if payload.location_id is not None:
        location = principal.db.get(Location, payload.location_id)
        if location is None or location.company_id != principal.tenant_id:
            raise NotFound("Location not found")

    duplicate = principal.db.scalar(
        select(Holiday).where(
            Holiday.company_id == principal.tenant_id,
            Holiday.date == payload.date,
            Holiday.name == payload.name,
            Holiday.location_id.is_(payload.location_id)
            if payload.location_id is None
            else Holiday.location_id == payload.location_id,
        )
    )
    if duplicate:
        raise Conflict(f"'{payload.name}' is already declared on {payload.date}")

    holiday = Holiday(company_id=principal.tenant_id, **payload.model_dump())
    principal.db.add(holiday)
    principal.db.commit()
    principal.db.refresh(holiday)
    return holiday


@router.post("/bulk", response_model=list[HolidayOut], status_code=status.HTTP_201_CREATED)
def create_holidays_bulk(payload: list[HolidayCreate], principal: ManageAccess):
    """Load a full year's calendar in one call. Existing entries are skipped."""
    created = []
    for item in payload:
        exists = principal.db.scalar(
            select(Holiday).where(
                Holiday.company_id == principal.tenant_id,
                Holiday.date == item.date,
                Holiday.name == item.name,
            )
        )
        if exists:
            continue
        holiday = Holiday(company_id=principal.tenant_id, **item.model_dump())
        principal.db.add(holiday)
        created.append(holiday)
    principal.db.commit()
    for holiday in created:
        principal.db.refresh(holiday)
    return created


@router.patch("/{holiday_id}", response_model=HolidayOut)
def update_holiday(
    holiday_id: int, payload: HolidayUpdate, principal: ManageAccess
):
    holiday = principal.db.get(Holiday, holiday_id)
    if holiday is None or holiday.company_id != principal.tenant_id:
        raise NotFound("Holiday not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(holiday, field, value)
    principal.db.commit()
    principal.db.refresh(holiday)
    return holiday


@router.delete("/{holiday_id}", response_model=Message)
def delete_holiday(holiday_id: int, principal: ManageAccess):
    holiday = principal.db.get(Holiday, holiday_id)
    if holiday is None or holiday.company_id != principal.tenant_id:
        raise NotFound("Holiday not found")
    principal.db.delete(holiday)
    principal.db.commit()
    return Message(message="Holiday deleted")
