from datetime import date, time

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin
from app.models.enums import HolidayType, enum_column


class WorkPolicy(Base, PKMixin, TimestampMixin):
    __tablename__ = "work_policies"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_workpolicy_company_name"),)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Default Work Policy")

    # ISO weekday numbers: Monday=1 ... Sunday=7
    working_days: Mapped[list[int]] = mapped_column(JSON, default=lambda: [1, 2, 3, 4, 5])

    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_start: Mapped[time | None] = mapped_column(Time)
    break_end: Mapped[time | None] = mapped_column(Time)

    full_day_hours: Mapped[float] = mapped_column(Numeric(4, 2), default=8, nullable=False)
    half_day_hours: Mapped[float] = mapped_column(Numeric(4, 2), default=4, nullable=False)
    late_grace_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)

    is_default: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def weekly_off_days(self) -> list[int]:
        return [d for d in range(1, 8) if d not in (self.working_days or [])]


class LeaveType(Base, PKMixin, TimestampMixin):
    __tablename__ = "leave_types"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_leavetype_company_code"),)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    annual_quota: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)

    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_half_day: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    carry_forward: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_carry_forward: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    requires_attachment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LeaveBalance(Base, PKMixin, TimestampMixin):
    __tablename__ = "leave_balances"
    __table_args__ = (
        UniqueConstraint("employee_id", "leave_type_id", "year", name="uq_leave_balance"),
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_type_id: Mapped[int] = mapped_column(
        ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    allocated: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    carried_forward: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    used: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    pending: Mapped[float] = mapped_column(Numeric(6, 2), default=0, nullable=False)

    leave_type: Mapped[LeaveType] = relationship(lazy="joined")

    @property
    def total(self) -> float:
        return float(self.allocated) + float(self.carried_forward)

    @property
    def available(self) -> float:
        return self.total - float(self.used) - float(self.pending)


class Holiday(Base, PKMixin, TimestampMixin):
    __tablename__ = "holidays"
    __table_args__ = (
        UniqueConstraint("company_id", "date", "name", "location_id", name="uq_holiday"),
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    holiday_type: Mapped[HolidayType] = mapped_column(
        enum_column(HolidayType), default=HolidayType.PUBLIC, nullable=False
    )
    # NULL location => applies to every location in the company.
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE")
    )
    description: Mapped[str | None] = mapped_column(String(500))

    location: Mapped["Location | None"] = relationship()  # noqa: F821
