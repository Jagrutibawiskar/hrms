from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin
from app.models.enums import DocumentType, enum_column


class EmployeeDocument(Base, PKMixin, TimestampMixin):
    __tablename__ = "employee_documents"
    __table_args__ = (Index("ix_document_company_employee", "company_id", "employee_id"),)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )

    document_type: Mapped[DocumentType] = mapped_column(
        enum_column(DocumentType), default=DocumentType.OTHER, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # When false the document is HR-internal and hidden from the employee.
    is_visible_to_employee: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    employee: Mapped["Employee"] = relationship(lazy="joined")  # noqa: F821
