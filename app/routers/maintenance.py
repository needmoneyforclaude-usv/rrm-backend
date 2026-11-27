from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Maintenance, Resource, User
from app.schemas import (MaintenanceCreated, MaintenanceIn, MaintenanceOut,
                         ReservationOut)
from app.services.notifications import notify_team
from app.services.reservations import (ACTIVE_STATUSES, describe,
                                       overlapping_reservations)

router = APIRouter(prefix="/api/resources", tags=["Maintenance"])


def _get_resource(db: Session, resource_id: int) -> Resource:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resursa nu exista")
    return resource


@router.get("/{resource_id}/maintenance",
            response_model=list[MaintenanceOut])
def get_resource_maintenance(resource_id: int,
                             db: Session = Depends(get_db)):
    _get_resource(db, resource_id)
    query = (select(Maintenance)
             .where(Maintenance.resource_id == resource_id)
             .order_by(Maintenance.start_time))
    return db.scalars(query).all()


@router.get("/{resource_id}/maintenance/affected-reservations",
            response_model=list[ReservationOut])
def get_affected_reservations(resource_id: int, start_time: datetime,
                              end_time: datetime,
                              _admin=Depends(require_roles("ADMIN")),
                              db: Session = Depends(get_db)):
    _get_resource(db, resource_id)
    if end_time <= start_time:
        raise HTTPException(
            status_code=400,
            detail="Ora de sfarsit trebuie sa fie dupa ora de start",
        )
    return overlapping_reservations(db, resource_id, start_time, end_time,
                                    ACTIVE_STATUSES)


@router.post("/{resource_id}/maintenance",
             response_model=MaintenanceCreated, status_code=201)
def create_maintenance(resource_id: int, data: MaintenanceIn,
                       admin: User = Depends(require_roles("ADMIN")),
                       db: Session = Depends(get_db)):
    _get_resource(db, resource_id)
    maintenance = Maintenance(resource_id=resource_id,
                              start_time=data.start_time,
                              end_time=data.end_time,
                              reason=data.reason,
                              admin_id=admin.id)
    db.add(maintenance)

    affected = overlapping_reservations(db, resource_id, data.start_time,
                                        data.end_time, ACTIVE_STATUSES)
    for reservation in affected:
        reservation.status = "CANCELLED"
        notify_team(db, reservation.team_id,
                    "Rezervare anulata din cauza mentenantei: "
                    f"{describe(reservation)}",
                    reservation.id)
    db.commit()
    db.refresh(maintenance)
    return MaintenanceCreated(
        maintenance=MaintenanceOut.model_validate(maintenance),
        cancelled_reservations=len(affected),
    )


periods_router = APIRouter(prefix="/api/maintenance", tags=["Maintenance"])


@periods_router.delete("/{maintenance_id}", status_code=204)
def delete_maintenance(maintenance_id: int,
                       _admin=Depends(require_roles("ADMIN")),
                       db: Session = Depends(get_db)):
    maintenance = db.get(Maintenance, maintenance_id)
    if maintenance is None:
        raise HTTPException(status_code=404,
                            detail="Perioada de mentenanta nu exista")
    db.delete(maintenance)
    db.commit()
