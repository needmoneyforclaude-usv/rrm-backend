"""Logica de disponibilitate: verificarea suprapunerilor (no overlap).

Doua intervale [a_start, a_end) si [b_start, b_end) se suprapun daca
a_start < b_end si a_end > b_start.
"""
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import Maintenance, Reservation

ACTIVE_STATUSES = ("PENDING", "CONFIRMED")
PENDING_MINUTES = 10


def pending_expired(reservation: Reservation) -> bool:
    if reservation.status != "PENDING" or reservation.created_at is None:
        return False
    limit = reservation.created_at + timedelta(minutes=PENDING_MINUTES)
    return datetime.now() > limit


def overlapping_reservations(db: Session, resource_id: int,
                             start_time: datetime, end_time: datetime,
                             exclude_id: int | None = None
                             ) -> list[Reservation]:
    query = select(Reservation).where(
        Reservation.resource_id == resource_id,
        or_(
            Reservation.status == "CONFIRMED",
            and_(Reservation.status == "PENDING",
                 Reservation.created_at > datetime.now()
                 - timedelta(minutes=PENDING_MINUTES)),
        ),
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
    """Intoarce motivul conflictului sau None daca intervalul e liber."""
    if overlapping_maintenance(db, resource_id, start_time, end_time):
        return "Resursa este in mentenanta in intervalul ales"
    if overlapping_reservations(db, resource_id, start_time, end_time,
                                exclude_id):
        return "Intervalul este deja rezervat"
    return None


def describe(reservation: Reservation) -> str:
    """Text scurt pentru notificari, ex: 'Sala C204, 20.11.2026 10:00-12:00'."""
    start, end = reservation.start_time, reservation.end_time
    interval = f"{start:%d.%m.%Y %H:%M}-{end:%H:%M}"
    if start.date() != end.date():
        interval = f"{start:%d.%m.%Y %H:%M} - {end:%d.%m.%Y %H:%M}"
    return f"{reservation.resource_name}, {interval}"
