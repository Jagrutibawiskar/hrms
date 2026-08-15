from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.deps import CurrentUser
from app.core.exceptions import NotFound
from app.core.pagination import Page, Pagination, build_page, paginate
from app.models.notification import Notification
from app.schemas.common import Message
from app.schemas.misc import MarkReadRequest, NotificationCount, NotificationOut
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=Page[NotificationOut])
def list_notifications(
    pagination: Pagination,
    principal: CurrentUser,
    unread_only: bool = Query(False),
):
    stmt = select(Notification).where(Notification.user_id == principal.user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
    rows, total = paginate(principal.db, stmt, pagination)
    return build_page(rows, total, pagination)


@router.get("/count", response_model=NotificationCount)
def count(principal: CurrentUser):
    total = principal.db.scalar(
        select(func.count(Notification.id)).where(Notification.user_id == principal.user_id)
    )
    unread = principal.db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == principal.user_id, Notification.is_read.is_(False)
        )
    )
    return NotificationCount(unread=unread or 0, total=total or 0)


@router.post("/read", response_model=Message)
def mark_read(payload: MarkReadRequest, principal: CurrentUser):
    """Marks the given notifications read, or every unread one when no ids are sent."""
    updated = notification_service.mark_read(
        principal.db, principal.user_id, payload.notification_ids
    )
    principal.db.commit()
    return Message(message=f"{updated} notification(s) marked as read")


@router.delete("/{notification_id}", response_model=Message)
def delete_notification(notification_id: int, principal: CurrentUser):
    row = principal.db.get(Notification, notification_id)
    if row is None or row.user_id != principal.user_id:
        raise NotFound("Notification not found")
    principal.db.delete(row)
    principal.db.commit()
    return Message(message="Notification deleted")
