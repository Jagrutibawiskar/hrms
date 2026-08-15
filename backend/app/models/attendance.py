from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin
from app.models.enums import AttendanceLogType, AttendanceStatus, enum_column


class Attendance(Base, PKMixin, TimestampMixin):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_attendance_employee_date"),
        Index("ix_attendance_company_date", "company_id", "date"),
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)

    check_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    working_hours: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)

    status: Mapped[AttendanceStatus] = mapped_column(
        enum_column(AttendanceStatus), default=AttendanceStatus.ABSENT, nullable=False
    )
    is_late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    late_minutes: Mapped[int] = mapped_column(Numeric(6, 0), default=0, nullable=False)

    is_regularized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    regularized_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    remarks: Mapped[str | None] = mapped_column(String(500))

    # Where the punch happened, for geofenced attendance.
    check_in_lat: Mapped[float | None] = mapped_column(Float)
    check_in_lng: Mapped[float | None] = mapped_column(Float)
    check_out_lat: Mapped[float | None] = mapped_column(Float)
    check_out_lng: Mapped[float | None] = mapped_column(Float)
    check_in_distance_m: Mapped[float | None] = mapped_column(Float)

    employee: Mapped["Employee"] = relationship(lazy="joined")  # noqa: F821
    logs: Mapped[list["AttendanceLog"]] = relationship(
        back_populates="attendance", cascade="all, delete-orphan"
    )


class AttendanceLog(Base, PKMixin):
    __tablename__ = "attendance_logs"
    __table_args__ = (Index("ix_attendance_logs_employee", "employee_id", "logged_at"),)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    attendance_id: Mapped[int] = mapped_column(
        ForeignKey("attendance.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )

    log_type: Mapped[AttendanceLogType] = mapped_column(
        enum_column(AttendanceLogType), nullable=False
    )
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="WEB", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))

    attendance: Mapped[Attendance] = relationship(back_populates="logs")
