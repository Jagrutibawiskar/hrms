from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin


class Department(Base, PKMixin, TimestampMixin):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_department_company_name"),)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(String(500))
    head_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL", use_alter=True)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped["Company"] = relationship(back_populates="departments")  # noqa: F821
    head: Mapped["Employee | None"] = relationship(  # noqa: F821
        foreign_keys=[head_employee_id], post_update=True
    )


class Designation(Base, PKMixin, TimestampMixin):
    __tablename__ = "designations"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_designation_company_name"),)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    level: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    department: Mapped[Department | None] = relationship()


class Location(Base, PKMixin, TimestampMixin):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_location_company_name"),)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    timezone: Mapped[str | None] = mapped_column(String(64))
    is_headquarters: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Geofenced attendance: employees must be within `geofence_radius_m` of this
    # point to punch in or out. Null coordinates mean the location is unfenced.
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    geofence_radius_m: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    @property
    def has_geofence(self) -> bool:
        return self.latitude is not None and self.longitude is not None
