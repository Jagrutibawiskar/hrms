from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin
from app.models.enums import (
    EmployeeStatus,
    EmploymentType,
    Gender,
    MaritalStatus,
    ProfileStatus,
    WorkMode,
    enum_column,
)


class Employee(Base, PKMixin, TimestampMixin):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("company_id", "employee_code", name="uq_employee_company_code"),
        UniqueConstraint("company_id", "work_email", name="uq_employee_company_email"),
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )

    employee_code: Mapped[str] = mapped_column(String(40), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    work_email: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_photo_path: Mapped[str | None] = mapped_column(String(500))

    status: Mapped[EmployeeStatus] = mapped_column(
        enum_column(EmployeeStatus), default=EmployeeStatus.ACTIVE, nullable=False
    )
    # DRAFT while HR is still collecting details/documents; COMPLETE once the
    # company's document policy is satisfied.
    profile_status: Mapped[ProfileStatus] = mapped_column(
        enum_column(ProfileStatus), default=ProfileStatus.COMPLETE, nullable=False, index=True
    )

    user: Mapped["User | None"] = relationship(back_populates="employee")  # noqa: F821
    company: Mapped["Company"] = relationship(back_populates="employees")  # noqa: F821
    personal: Mapped["EmployeePersonalDetail | None"] = relationship(
        back_populates="employee", cascade="all, delete-orphan", uselist=False, lazy="joined"
    )
    employment: Mapped["EmployeeEmploymentDetail | None"] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
        foreign_keys="EmployeeEmploymentDetail.employee_id",
    )

    @property
    def full_name(self) -> str:
        return " ".join(filter(None, [self.first_name, self.last_name]))

    @property
    def is_active(self) -> bool:
        return self.status in (
            EmployeeStatus.ACTIVE,
            EmployeeStatus.PROBATION,
            EmployeeStatus.NOTICE_PERIOD,
        )


class EmployeePersonalDetail(Base, PKMixin, TimestampMixin):
    __tablename__ = "employee_personal_details"

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[Gender | None] = mapped_column(enum_column(Gender))
    marital_status: Mapped[MaritalStatus | None] = mapped_column(enum_column(MaritalStatus))
    blood_group: Mapped[str | None] = mapped_column(String(10))
    nationality: Mapped[str | None] = mapped_column(String(80))
    personal_email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    alternate_phone: Mapped[str | None] = mapped_column(String(30))

    address_line1: Mapped[str | None] = mapped_column(String(255))
    address_line2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))

    emergency_contact_name: Mapped[str | None] = mapped_column(String(150))
    emergency_contact_relation: Mapped[str | None] = mapped_column(String(60))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(30))

    employee: Mapped[Employee] = relationship(back_populates="personal")


class EmployeeEmploymentDetail(Base, PKMixin, TimestampMixin):
    __tablename__ = "employee_employment_details"

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True
    )
    designation_id: Mapped[int | None] = mapped_column(
        ForeignKey("designations.id", ondelete="SET NULL")
    )
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), index=True
    )
    work_policy_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_policies.id", ondelete="SET NULL")
    )

    joining_date: Mapped[date] = mapped_column(Date, nullable=False)
    confirmation_date: Mapped[date | None] = mapped_column(Date)
    probation_months: Mapped[int | None] = mapped_column(Integer)
    employment_type: Mapped[EmploymentType] = mapped_column(
        enum_column(EmploymentType), default=EmploymentType.FULL_TIME, nullable=False
    )
    work_mode: Mapped[WorkMode] = mapped_column(
        enum_column(WorkMode), default=WorkMode.OFFICE, nullable=False
    )
    is_manager: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    exit_date: Mapped[date | None] = mapped_column(Date)
    exit_reason: Mapped[str | None] = mapped_column(String(500))

    employee: Mapped[Employee] = relationship(
        back_populates="employment", foreign_keys=[employee_id]
    )
    manager: Mapped[Employee | None] = relationship(foreign_keys=[manager_id])
    department: Mapped["Department | None"] = relationship(lazy="joined")  # noqa: F821
    designation: Mapped["Designation | None"] = relationship(lazy="joined")  # noqa: F821
    location: Mapped["Location | None"] = relationship(lazy="joined")  # noqa: F821
