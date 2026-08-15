"""Import every model here so `Base.metadata` is complete for Alembic and create_all."""

from app.models.attendance import Attendance, AttendanceLog
from app.models.base import Base
from app.models.company import Company
from app.models.compliance import CompanyCompliance
from app.models.document import EmployeeDocument
from app.models.employee import (
    Employee,
    EmployeeEmploymentDetail,
    EmployeePersonalDetail,
)
from app.models.leave import LeaveRequest
from app.models.notification import AuditLog, Notification
from app.models.organization import Department, Designation, Location
from app.models.payroll import (
    EmployeeSalary,
    EmployeeSalaryComponent,
    PayrollItem,
    PayrollRun,
    Payslip,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureComponent,
)
from app.models.policy import Holiday, LeaveBalance, LeaveType, WorkPolicy
from app.models.user import Permission, Role, RolePermission, User, UserRole

__all__ = [
    "Base",
    "Attendance",
    "AttendanceLog",
    "AuditLog",
    "Company",
    "CompanyCompliance",
    "Department",
    "Designation",
    "Employee",
    "EmployeeDocument",
    "EmployeeEmploymentDetail",
    "EmployeePersonalDetail",
    "EmployeeSalary",
    "EmployeeSalaryComponent",
    "Holiday",
    "LeaveBalance",
    "LeaveRequest",
    "LeaveType",
    "Location",
    "Notification",
    "PayrollItem",
    "PayrollRun",
    "Payslip",
    "Permission",
    "Role",
    "RolePermission",
    "SalaryComponent",
    "SalaryStructure",
    "SalaryStructureComponent",
    "User",
    "UserRole",
    "WorkPolicy",
]
