from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin
from app.models.enums import CalculationType, ComponentType, PayrollStatus, enum_column


class SalaryComponent(Base, PKMixin, TimestampMixin):
    __tablename__ = "salary_components"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_salary_component_code"),)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    component_type: Mapped[ComponentType] = mapped_column(
        enum_column(ComponentType), nullable=False
    )
    calculation_type: Mapped[CalculationType] = mapped_column(
        enum_column(CalculationType), default=CalculationType.FIXED, nullable=False
    )
    default_value: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Deductions/earnings that should not shrink when the employee has LOP days.
    prorate_on_lop: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SalaryStructure(Base, PKMixin, TimestampMixin):
    __tablename__ = "salary_structures"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_salary_structure_name"),)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    components: Mapped[list["SalaryStructureComponent"]] = relationship(
        back_populates="structure", cascade="all, delete-orphan", lazy="selectin"
    )


class SalaryStructureComponent(Base, PKMixin):
    __tablename__ = "salary_structure_components"
    __table_args__ = (
        UniqueConstraint("structure_id", "component_id", name="uq_structure_component"),
    )

    structure_id: Mapped[int] = mapped_column(
        ForeignKey("salary_structures.id", ondelete="CASCADE"), nullable=False
    )
    component_id: Mapped[int] = mapped_column(
        ForeignKey("salary_components.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    structure: Mapped[SalaryStructure] = relationship(back_populates="components")
    component: Mapped[SalaryComponent] = relationship(lazy="joined")


class EmployeeSalary(Base, PKMixin, TimestampMixin):
    __tablename__ = "employee_salaries"
    __table_args__ = (Index("ix_employee_salary_active", "employee_id", "is_active"),)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    structure_id: Mapped[int | None] = mapped_column(
        ForeignKey("salary_structures.id", ondelete="SET NULL")
    )

    ctc: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    gross_monthly: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    deductions_monthly: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    net_monthly: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    payment_mode: Mapped[str | None] = mapped_column(String(30))
    bank_account_number: Mapped[str | None] = mapped_column(String(40))
    bank_ifsc: Mapped[str | None] = mapped_column(String(20))

    components: Mapped[list["EmployeeSalaryComponent"]] = relationship(
        back_populates="salary", cascade="all, delete-orphan", lazy="selectin"
    )
    employee: Mapped["Employee"] = relationship(lazy="joined")  # noqa: F821


class EmployeeSalaryComponent(Base, PKMixin):
    __tablename__ = "employee_salary_components"
    __table_args__ = (
        UniqueConstraint("employee_salary_id", "component_id", name="uq_emp_salary_component"),
    )

    employee_salary_id: Mapped[int] = mapped_column(
        ForeignKey("employee_salaries.id", ondelete="CASCADE"), nullable=False
    )
    component_id: Mapped[int] = mapped_column(
        ForeignKey("salary_components.id", ondelete="CASCADE"), nullable=False
    )
    monthly_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    salary: Mapped[EmployeeSalary] = relationship(back_populates="components")
    component: Mapped[SalaryComponent] = relationship(lazy="joined")


class PayrollRun(Base, PKMixin, TimestampMixin):
    __tablename__ = "payroll_runs"
    __table_args__ = (UniqueConstraint("company_id", "year", "month", name="uq_payroll_run_period"),)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[PayrollStatus] = mapped_column(
        enum_column(PayrollStatus), default=PayrollStatus.DRAFT, nullable=False
    )
    employee_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_gross: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    total_deductions: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    total_net: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)

    processed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(1000))

    items: Mapped[list["PayrollItem"]] = relationship(
        back_populates="payroll_run", cascade="all, delete-orphan"
    )


class PayrollItem(Base, PKMixin, TimestampMixin):
    __tablename__ = "payroll_items"
    __table_args__ = (
        UniqueConstraint("payroll_run_id", "employee_id", name="uq_payroll_item_employee"),
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payroll_run_id: Mapped[int] = mapped_column(
        ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )

    working_days: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    paid_days: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    lop_days: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)

    gross_earnings: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_deductions: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    net_pay: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    earnings_breakdown: Mapped[list[dict]] = mapped_column(JSON, default=list)
    deductions_breakdown: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # Why the LOP days were charged: absences, unpaid leave, half-days.
    lop_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)

    payroll_run: Mapped[PayrollRun] = relationship(back_populates="items")
    employee: Mapped["Employee"] = relationship(lazy="joined")  # noqa: F821


class Payslip(Base, PKMixin, TimestampMixin):
    __tablename__ = "payslips"
    __table_args__ = (
        UniqueConstraint("payroll_item_id", name="uq_payslip_item"),
        Index("ix_payslip_employee_period", "employee_id", "year", "month"),
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payroll_run_id: Mapped[int] = mapped_column(
        ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False
    )
    payroll_item_id: Mapped[int] = mapped_column(
        ForeignKey("payroll_items.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )

    payslip_number: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    net_pay: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_path: Mapped[str | None] = mapped_column(String(500))

    payroll_item: Mapped[PayrollItem] = relationship(lazy="joined")
    employee: Mapped["Employee"] = relationship(lazy="joined")  # noqa: F821
