from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin


class CompanyCompliance(Base, PKMixin, TimestampMixin):
    """Statutory registration details and which deductions apply to this company.

    Payroll reads the `*_enabled` flags to decide whether to apply PF, ESI, PT and
    TDS, so switching one off here stops it appearing on the next payslip.
    """

    __tablename__ = "company_compliance"

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    # Provident Fund
    pf_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pf_number: Mapped[str | None] = mapped_column(String(60))
    pf_employee_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=12, nullable=False)
    pf_employer_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=12, nullable=False)
    pf_wage_ceiling: Mapped[float] = mapped_column(Numeric(12, 2), default=15000, nullable=False)

    # Employee State Insurance
    esi_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    esi_number: Mapped[str | None] = mapped_column(String(60))
    esi_employee_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0.75, nullable=False)
    esi_employer_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=3.25, nullable=False)
    esi_wage_ceiling: Mapped[float] = mapped_column(Numeric(12, 2), default=21000, nullable=False)

    # Professional Tax (state-levied)
    pt_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pt_state: Mapped[str | None] = mapped_column(String(80))
    pt_monthly_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=200, nullable=False)

    # Tax deducted at source
    tds_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tan: Mapped[str | None] = mapped_column(String(20))

    # Company registration identifiers
    pan: Mapped[str | None] = mapped_column(String(20))
    gstin: Mapped[str | None] = mapped_column(String(20))
    cin: Mapped[str | None] = mapped_column(String(30))
    labour_licence_number: Mapped[str | None] = mapped_column(String(60))

    # Shops & Establishments / working-hours compliance
    max_weekly_hours: Mapped[float] = mapped_column(Numeric(5, 2), default=48, nullable=False)
    min_break_minutes: Mapped[int] = mapped_column(Numeric(5, 0), default=30, nullable=False)
