from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification, User

MAX_MESSAGE_LENGTH = 255


def notify_user(db: Session, user_id: int, message: str,
                reservation_id: int | None = None) -> Notification:
    notification = Notification(user_id=user_id,
                                reservation_id=reservation_id,
                                message=message[:MAX_MESSAGE_LENGTH],
                                is_read=False)
    db.add(notification)
    return notification


def notify_team(db: Session, team_id: int, message: str,
                reservation_id: int | None = None) -> int:
    member_ids = db.scalars(select(User.id).where(User.team_id == team_id))
    count = 0
    for member_id in member_ids:
        notify_user(db, member_id, message, reservation_id)
        count += 1
    return count


def notify_admins(db: Session, message: str,
                  reservation_id: int | None = None) -> int:
    admin_ids = db.scalars(select(User.id).where(User.role == "ADMIN"))
    count = 0
    for admin_id in admin_ids:
        notify_user(db, admin_id, message, reservation_id)
        count += 1
    return count
