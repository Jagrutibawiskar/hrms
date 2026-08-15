from datetime import date as date_type
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus, DocumentType, NotificationEvent
from app.schemas.common import ORMModel


class DocumentOut(ORMModel):
    id: int
    employee_id: int
    employee_name: str | None = None
    employee_code: str | None = None
    document_type: DocumentType
    title: str
    description: str | None
    file_name: str
    mime_type: str | None
    size_bytes: int
    is_visible_to_employee: bool
    uploaded_by_user_id: int | None
    created_at: datetime
    # Verification
    status: DocumentStatus = DocumentStatus.PENDING
    verified_by_user_id: int | None = None
    verified_at: datetime | None = None
    rejection_reason: str | None = None
    expiry_date: date_type | None = None


class DocumentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    document_type: DocumentType | None = None
    is_visible_to_employee: bool | None = None


class NotificationOut(ORMModel):
    id: int
    event_type: NotificationEvent
    title: str
    message: str
    entity_type: str | None
    entity_id: int | None
    action_url: str | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationCount(BaseModel):
    unread: int
    total: int


class MarkReadRequest(BaseModel):
    notification_ids: list[int] | None = None


# ---------------------------------------------------------------- dashboard


class DashboardCounts(BaseModel):
    total_employees: int
    active_employees: int
    present_today: int
    absent_today: int
    on_leave_today: int
    late_today: int
    wfh_today: int


class PendingItems(BaseModel):
    pending_leave_requests: int
    pending_payroll_runs: int


class MiniEmployee(BaseModel):
    id: int
    employee_code: str
    full_name: str
    department_name: str | None = None
    designation_name: str | None = None
    date: date_type | None = None


class MiniHoliday(BaseModel):
    id: int
    name: str
    date: date_type
    holiday_type: str


class HrDashboard(BaseModel):
    counts: DashboardCounts
    pending: PendingItems
    new_joiners: list[MiniEmployee] = []
    upcoming_birthdays: list[MiniEmployee] = []
    upcoming_holidays: list[MiniHoliday] = []
    recent_leave_requests: list[dict] = []


class EmployeeDashboard(BaseModel):
    employee_id: int
    full_name: str
    today: dict
    leave_balances: list[dict] = []
    pending_leaves: int
    upcoming_holidays: list[MiniHoliday] = []
    unread_notifications: int
    attendance_this_month: dict


# ---------------------------------------------------------------- reports


class ReportFilters(BaseModel):
    from_date: date_type | None = None
    to_date: date_type | None = None
    department_id: int | None = None
    employee_id: int | None = None
    status: str | None = None
    export: bool = Field(default=False, description="Return CSV instead of JSON")
