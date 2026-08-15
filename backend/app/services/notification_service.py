from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.enums import NotificationEvent, RoleName
from app.models.notification import AuditLog, Notification
from app.models.user import User, UserRole
from app.utils.dates import utcnow


def notify(
    db: Session,
    *,
    company_id: int | None,
    user_id: int,
    event: NotificationEvent,
    title: str,
    message: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    action_url: str | None = None,
) -> Notification:
    n = Notification(
        company_id=company_id,
        user_id=user_id,
        event_type=event,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
        action_url=action_url,
    )
    db.add(n)
    return n


def notify_employee(db: Session, employee: Employee | None, **kwargs) -> Notification | None:
    """No-op when the employee has no login yet — nothing to deliver to."""
    if employee is None or employee.user_id is None:
        return None
    return notify(db, company_id=employee.company_id, user_id=employee.user_id, **kwargs)


def notify_roles(db: Session, company_id: int, roles: list[RoleName], **kwargs) -> int:
    """Fan out to every active user in the company holding one of `roles`."""
    from app.models.user import Role

    user_ids = set(
        db.scalars(
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                User.company_id == company_id,
                User.is_active.is_(True),
                Role.name.in_(roles),
            )
        )
    )
    for uid in user_ids:
        notify(db, company_id=company_id, user_id=uid, **kwargs)
    return len(user_ids)


def mark_read(db: Session, user_id: int, notification_ids: list[int] | None = None) -> int:
    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=utcnow())
    )
    if notification_ids:
        stmt = stmt.where(Notification.id.in_(notification_ids))
    result = db.execute(stmt)
    return result.rowcount or 0


def audit(
    db: Session,
    *,
    company_id: int | None,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    changes: dict | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(
        AuditLog(
            company_id=company_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
            ip_address=ip_address,
        )
    )
