from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin, utcnow
from app.models.enums import HalfDaySession, LeaveStatus, enum_column


class LeaveRequest(Base, PKMixin, TimestampMixin):
    __tablename__ = "leave_requests"
    __table_args__ = (
        Index("ix_leave_company_status", "company_id", "status"),
        Index("ix_leave_employee_dates", "employee_id", "from_date", "to_date"),
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    leave_type_id: Mapped[int] = mapped_column(
        ForeignKey("leave_types.id", ondelete="RESTRICT"), nullable=False
    )

    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_half_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    half_day_session: Mapped[HalfDaySession | None] = mapped_column(enum_column(HalfDaySession))
    days: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    attachment_path: Mapped[str | None] = mapped_column(String(500))
    contact_during_leave: Mapped[str | None] = mapped_column(String(60))

    status: Mapped[LeaveStatus] = mapped_column(
        enum_column(LeaveStatus), default=LeaveStatus.PENDING, nullable=False
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    approver_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"))
    actioned_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    actioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    action_comment: Mapped[str | None] = mapped_column(String(1000))

    employee: Mapped["Employee"] = relationship(  # noqa: F821
        foreign_keys=[employee_id], lazy="joined"
    )
    approver: Mapped["Employee | None"] = relationship(foreign_keys=[approver_id])  # noqa: F821
    leave_type: Mapped["LeaveType"] = relationship(lazy="joined")  # noqa: F821
