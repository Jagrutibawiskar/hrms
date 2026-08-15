from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import AttendanceStatus
from app.schemas.common import ORMModel


class CheckInRequest(BaseModel):
    remarks: str | None = Field(default=None, max_length=500)
    is_wfh: bool = False
    # Sent by the browser's Geolocation API when the company enforces a geofence.
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class CheckOutRequest(BaseModel):
    remarks: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class AttendanceOut(ORMModel):
    id: int
    employee_id: int
    employee_name: str | None = None
    employee_code: str | None = None
    date: date
    check_in: datetime | None
    check_out: datetime | None
    working_hours: float
    status: AttendanceStatus
    is_late: bool
    late_minutes: int
    is_regularized: bool
    remarks: str | None


class TodayAttendance(BaseModel):
    date: date
    server_time: datetime
    checked_in: bool
    checked_out: bool
    check_in: datetime | None = None
    check_out: datetime | None = None
    working_hours: float = 0
    status: AttendanceStatus | None = None
    is_working_day: bool = True
    is_holiday: bool = False
    holiday_name: str | None = None
    on_leave: bool = False
    # Geofence context so the UI knows whether to ask for location permission.
    geofence_enabled: bool = False
    geofence_location: str | None = None
    geofence_radius_m: int | None = None
    regularizations_used: int = 0
    regularizations_allowed: int = 3


class AttendanceRegularize(BaseModel):
    """HR override for a single day."""

    check_in: datetime | None = None
    check_out: datetime | None = None
    status: AttendanceStatus
    remarks: str = Field(min_length=1, max_length=500)


class AttendanceSummary(BaseModel):
    from_date: date
    to_date: date
    total_days: int
    working_days: int
    present: int
    absent: int
    half_day: int
    late: int
    leave: int
    holiday: int
    wfh: int
    weekend: int
    total_hours: float
    average_hours: float
