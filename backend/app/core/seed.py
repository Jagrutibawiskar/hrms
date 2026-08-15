"""Seeds the global (non-tenant) tables: roles, permissions and their mapping."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import ALL_PERMISSIONS, ROLE_PERMISSIONS
from app.models.enums import RoleName
from app.models.user import Permission, Role, RolePermission

ROLE_DESCRIPTIONS = {
    RoleName.SUPER_ADMIN: "Platform owner across all companies",
    RoleName.COMPANY_ADMIN: "Full access within their own company",
    RoleName.HR: "Manages people, attendance, leave, payroll and reports",
    RoleName.MANAGER: "Manages their own team and approves their leave",
    RoleName.EMPLOYEE: "Self-service access to their own records",
}


def seed_roles_and_permissions(db: Session) -> None:
    permissions: dict[str, Permission] = {
        p.code: p for p in db.scalars(select(Permission))
    }
    for code in ALL_PERMISSIONS:
        if code not in permissions:
            permission = Permission(code=code, description=code.replace(":", " ").replace("_", " "))
            db.add(permission)
            permissions[code] = permission
    db.flush()

    roles: dict[RoleName, Role] = {r.name: r for r in db.scalars(select(Role))}
    for name in RoleName:
        if name not in roles:
            role = Role(name=name, description=ROLE_DESCRIPTIONS[name])
            db.add(role)
            roles[name] = role
    db.flush()

    existing = {
        (rp.role_id, rp.permission_id) for rp in db.scalars(select(RolePermission))
    }
    for name, codes in ROLE_PERMISSIONS.items():
        role = roles[name]
        for code in codes:
            key = (role.id, permissions[code].id)
            if key not in existing:
                db.add(RolePermission(role_id=role.id, permission_id=permissions[code].id))
                existing.add(key)
    db.commit()
