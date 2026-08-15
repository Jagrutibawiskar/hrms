from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import HalfDaySession, LeaveStatus
from app.schemas.common import ORMModel


class LeaveApply(BaseModel):
    leave_type_id: int
    from_date: date
    to_date: date
    is_half_day: bool = False
    half_day_session: HalfDaySession | None = None
    reason: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def _check(self):
        if self.to_date < self.from_date:
            raise ValueError("to_date cannot be before from_date")
        if self.is_half_day:
            if self.from_date != self.to_date:
                raise ValueError("A half-day leave must start and end on the same date")
            if self.half_day_session is None:
                raise ValueError("half_day_session is required for a half-day leave")
        return self


class LeaveEdit(BaseModel):
    """HR/admin correction. Every field is optional — only what's sent is changed."""

    leave_type_id: int | None = None
    from_date: date | None = None
    to_date: date | None = None
    is_half_day: bool | None = None
    half_day_session: HalfDaySession | None = None
    reason: str | None = Field(default=None, min_length=3, max_length=1000)
    edit_note: str | None = Field(default=None, max_length=500)


class LeaveAction(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)


class LeaveRejectAction(BaseModel):
    comment: str = Field(min_length=1, max_length=1000)


class LeaveRequestOut(ORMModel):
    id: int
    employee_id: int
    employee_name: str | None = None
    employee_code: str | None = None
    leave_type_id: int
    leave_type_name: str | None = None
    from_date: date
    to_date: date
    is_half_day: bool
    half_day_session: HalfDaySession | None
    days: float
    reason: str
    attachment_path: str | None
    status: LeaveStatus
    applied_at: datetime
    approver_id: int | None
    approver_name: str | None = None
    actioned_at: datetime | None
    action_comment: str | None


class LeaveBalanceOut(BaseModel):
    leave_type_id: int
    leave_type_name: str
    leave_type_code: str
    is_paid: bool
    year: int
    allocated: float
    carried_forward: float
    used: float
    pending: float
    available: float
    total: float


class LeaveBalanceAdjust(BaseModel):
    employee_id: int
    leave_type_id: int
    year: int
    allocated: float = Field(ge=0, le=365)
    carried_forward: float = Field(default=0, ge=0)
