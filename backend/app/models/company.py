from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin
from app.models.enums import OnboardingStep, enum_column


class Company(Base, PKMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    company_size: Mapped[str] = mapped_column(String(20), nullable=False)
    company_type: Mapped[str | None] = mapped_column(String(100))

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    website: Mapped[str | None] = mapped_column(String(255))

    country: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)

    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    fiscal_year_start_month: Mapped[int] = mapped_column(Integer, default=4, nullable=False)

    logo_path: Mapped[str | None] = mapped_column(String(500))

    # Attendance policy knobs.
    geofence_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_regularizations_per_month: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Employee code generation, e.g. "EMP-{NUMBER}" -> EMP-0001. HR can override
    # per employee, but the sequence means they rarely have to.
    employee_id_format: Mapped[str] = mapped_column(
        String(40), default="EMP-{NUMBER}", nullable=False
    )
    employee_id_padding: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    employee_id_next: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    onboarding_step: Mapped[OnboardingStep] = mapped_column(
        enum_column(OnboardingStep), default=OnboardingStep.ORGANIZATION, nullable=False
    )
    is_onboarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True)
    )

    departments: Mapped[list["Department"]] = relationship(  # noqa: F821
        back_populates="company", cascade="all, delete-orphan"
    )
    employees: Mapped[list["Employee"]] = relationship(  # noqa: F821
        back_populates="company", cascade="all, delete-orphan"
    )
