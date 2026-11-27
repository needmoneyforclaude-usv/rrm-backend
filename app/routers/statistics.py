from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Maintenance, Reservation, Resource
from app.schemas import ResourceStats, WeekStats

router = APIRouter(prefix="/api/statistics", tags=["Statistics"])

HOURS_PER_WEEK = 5 * 12


def _overlap_hours(start: datetime, end: datetime, week_start: datetime,
                   week_end: datetime) -> float:
    start = max(start, week_start)
    end = min(end, week_end)
    return max((end - start).total_seconds() / 3600, 0)


@router.get("", response_model=WeekStats)
def get_week_statistics(week: date | None = None,
                        _admin=Depends(require_roles("ADMIN")),
                        db: Session = Depends(get_db)):
    week = week or date.today()
    monday = week - timedelta(days=week.weekday())
    week_start = datetime.combine(monday, time(0, 0))
    week_end = week_start + timedelta(days=7)

    reservations = db.scalars(select(Reservation).where(
        Reservation.status == "CONFIRMED",
        Reservation.start_time < week_end,
        Reservation.end_time > week_start,
    )).all()

    now = datetime.now()
    in_maintenance = len(set(db.scalars(
        select(Maintenance.resource_id).where(Maintenance.start_time <= now,
                                              Maintenance.end_time > now)
    )))

    stats = []
    for resource in db.scalars(select(Resource).order_by(Resource.name)):
        hours = sum(_overlap_hours(r.start_time, r.end_time, week_start,
                                   week_end)
                    for r in reservations if r.resource_id == resource.id)
        stats.append(ResourceStats(
            resource_id=resource.id,
            resource_name=resource.name,
            reserved_hours=round(hours, 1),
            occupancy_percent=round(min(hours / HOURS_PER_WEEK * 100, 100)),
        ))
    stats.sort(key=lambda s: s.occupancy_percent, reverse=True)

    return WeekStats(week_start=monday,
                     active_reservations=len(reservations),
                     in_maintenance=in_maintenance,
                     resources=stats)
