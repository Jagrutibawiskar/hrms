"""Bank, statutory and document-policy records used by the HR employee wizard."""

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin
from app.models.enums import DocumentType, enum_column


class EmployeeBankDetail(Base, PKMixin, TimestampMixin):
    """Payroll destination. Only salary-permitted roles may read the full number."""

    __tablename__ = "employee_bank_details"

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    bank_name: Mapped[str | None] = mapped_column(String(120))
    account_holder_name: Mapped[str | None] = mapped_column(String(150))
    account_number: Mapped[str | None] = mapped_column(String(40))
    ifsc: Mapped[str | None] = mapped_column(String(20))
    branch: Mapped[str | None] = mapped_column(String(150))

    @property
    def masked_account_number(self) -> str | None:
        """`XXXX XXXX 4521` — safe to show in listings and on screen."""
        if not self.account_number:
            return None
        tail = self.account_number[-4:]
        return f"XXXX XXXX {tail}"


class EmployeeStatutoryDetail(Base, PKMixin, TimestampMixin):
    """Indian statutory identifiers. Nothing is mandatory — eligibility drives it."""

    __tablename__ = "employee_statutory_details"

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    pan: Mapped[str | None] = mapped_column(String(20))

    pf_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uan: Mapped[str | None] = mapped_column(String(30))
    pf_number: Mapped[str | None] = mapped_column(String(40))

    esi_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    esi_number: Mapped[str | None] = mapped_column(String(40))

    professional_tax_state: Mapped[str | None] = mapped_column(String(80))


class DocumentPolicy(Base, PKMixin, TimestampMixin):
    """Which document types this company requires before an employee is complete.

    Per-company so one tenant can demand Aadhaar while another demands a work permit.
    """

    __tablename__ = "document_policies"
    __table_args__ = (
        UniqueConstraint("company_id", "document_type", name="uq_document_policy"),
    )

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[DocumentType] = mapped_column(enum_column(DocumentType), nullable=False)

    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Documents like a work permit or contract expire and need re-collection.
    tracks_expiry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
