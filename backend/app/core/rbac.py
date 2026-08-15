"""Permission registry and role -> permission mapping.

Permissions are stored in the DB (`permissions`, `role_permissions`) and seeded from
this file, so the mapping stays version-controlled while remaining queryable.
"""

from app.models.enums import RoleName


class P:
    COMPANY_READ = "company:read"
    COMPANY_UPDATE = "company:update"

    ORG_READ = "organization:read"
    ORG_MANAGE = "organization:manage"

    EMPLOYEE_READ_ALL = "employee:read_all"
    EMPLOYEE_READ_TEAM = "employee:read_team"
    EMPLOYEE_READ_SELF = "employee:read_self"
    EMPLOYEE_CREATE = "employee:create"
    EMPLOYEE_UPDATE = "employee:update"
    EMPLOYEE_DEACTIVATE = "employee:deactivate"

    ATTENDANCE_READ_ALL = "attendance:read_all"
    ATTENDANCE_READ_TEAM = "attendance:read_team"
    ATTENDANCE_READ_SELF = "attendance:read_self"
    ATTENDANCE_MARK_SELF = "attendance:mark_self"
    ATTENDANCE_MANAGE = "attendance:manage"

    LEAVE_READ_ALL = "leave:read_all"
    LEAVE_READ_TEAM = "leave:read_team"
    LEAVE_READ_SELF = "leave:read_self"
    LEAVE_APPLY = "leave:apply"
    LEAVE_APPROVE = "leave:approve"
    LEAVE_MANAGE = "leave:manage"

    HOLIDAY_READ = "holiday:read"
    HOLIDAY_MANAGE = "holiday:manage"

    DOCUMENT_READ_ALL = "document:read_all"
    DOCUMENT_READ_SELF = "document:read_self"
    DOCUMENT_MANAGE = "document:manage"

    PAYROLL_READ_ALL = "payroll:read_all"
    PAYROLL_READ_SELF = "payroll:read_self"
    PAYROLL_PROCESS = "payroll:process"
    PAYROLL_APPROVE = "payroll:approve"
    SALARY_READ = "salary:read"
    SALARY_MANAGE = "salary:manage"

    REPORT_VIEW = "report:view"
    DASHBOARD_HR = "dashboard:hr"

    SETTINGS_MANAGE = "settings:manage"
    USER_MANAGE = "user:manage"


ALL_PERMISSIONS: list[str] = sorted(
    v for k, v in vars(P).items() if not k.startswith("_") and isinstance(v, str)
)

SELF_SERVICE = {
    P.EMPLOYEE_READ_SELF,
    P.ATTENDANCE_READ_SELF,
    P.ATTENDANCE_MARK_SELF,
    P.LEAVE_READ_SELF,
    P.LEAVE_APPLY,
    P.DOCUMENT_READ_SELF,
    P.PAYROLL_READ_SELF,
    P.HOLIDAY_READ,
    P.COMPANY_READ,
    P.ORG_READ,
}

MANAGER_EXTRA = {
    P.EMPLOYEE_READ_TEAM,
    P.ATTENDANCE_READ_TEAM,
    P.LEAVE_READ_TEAM,
    P.LEAVE_APPROVE,
}

HR_EXTRA = {
    P.EMPLOYEE_READ_ALL,
    P.EMPLOYEE_CREATE,
    P.EMPLOYEE_UPDATE,
    P.EMPLOYEE_DEACTIVATE,
    P.ATTENDANCE_READ_ALL,
    P.ATTENDANCE_MANAGE,
    P.LEAVE_READ_ALL,
    P.LEAVE_MANAGE,
    P.HOLIDAY_MANAGE,
    P.DOCUMENT_READ_ALL,
    P.DOCUMENT_MANAGE,
    P.PAYROLL_READ_ALL,
    P.PAYROLL_PROCESS,
    P.SALARY_READ,
    P.SALARY_MANAGE,
    P.REPORT_VIEW,
    P.DASHBOARD_HR,
    P.ORG_MANAGE,
}

ROLE_PERMISSIONS: dict[RoleName, set[str]] = {
    RoleName.SUPER_ADMIN: set(ALL_PERMISSIONS),
    RoleName.COMPANY_ADMIN: set(ALL_PERMISSIONS),
    RoleName.HR: SELF_SERVICE | MANAGER_EXTRA | HR_EXTRA,
    RoleName.MANAGER: SELF_SERVICE | MANAGER_EXTRA,
    RoleName.EMPLOYEE: set(SELF_SERVICE),
}


def permissions_for_roles(role_names: list[str]) -> set[str]:
    granted: set[str] = set()
    for name in role_names:
        try:
            granted |= ROLE_PERMISSIONS[RoleName(name)]
        except ValueError:
            continue
    return granted
