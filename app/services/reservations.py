from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Maintenance, Reservation

ACTIVE_STATUSES = ("PENDING", "CONFIRMED")


def expire_past_pending(db: Session) -> None:
    db.execute(
        update(Reservation)
        .where(Reservation.status == "PENDING",
               Reservation.start_time <= datetime.now())
        .values(status="EXPIRED")
    )
    db.flush()


def overlapping_reservations(db: Session, resource_id: int,
                             start_time: datetime, end_time: datetime,
                             statuses: tuple[str, ...] = ("CONFIRMED",),
                             exclude_id: int | None = None
                             ) -> list[Reservation]:
    query = select(Reservation).where(
        Reservation.resource_id == resource_id,
        Reservation.status.in_(statuses),
        Reservation.start_time < end_time,
        Reservation.end_time > start_time,
    )
    if exclude_id is not None:
        query = query.where(Reservation.id != exclude_id)
    return list(db.scalars(query.order_by(Reservation.start_time)))


def overlapping_maintenance(db: Session, resource_id: int,
                            start_time: datetime, end_time: datetime
                            ) -> list[Maintenance]:
    query = select(Maintenance).where(
        Maintenance.resource_id == resource_id,
        Maintenance.start_time < end_time,
        Maintenance.end_time > start_time,
    )
    return list(db.scalars(query.order_by(Maintenance.start_time)))


def find_conflict(db: Session, resource_id: int, start_time: datetime,
                  end_time: datetime,
                  exclude_id: int | None = None) -> str | None:
    if overlapping_maintenance(db, resource_id, start_time, end_time):
        return "Resursa este in mentenanta in intervalul ales"
    if overlapping_reservations(db, resource_id, start_time, end_time,
                                exclude_id=exclude_id):
        return "Intervalul este deja rezervat"
    return None


def describe(reservation: Reservation) -> str:
    start, end = reservation.start_time, reservation.end_time
    interval = f"{start:%d.%m.%Y %H:%M}-{end:%H:%M}"
    if start.date() != end.date():
        interval = f"{start:%d.%m.%Y %H:%M} - {end:%d.%m.%Y %H:%M}"
    return f"{reservation.resource_name}, {interval}"
