from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_optional_user, require_roles
from app.models import Reservation, Resource, Team, User
from app.schemas import (CancelIn, QuoteOut, RejectIn, ReservationIn,
                         ReservationOut, SlotOut)
from app.services.notifications import notify_admins, notify_team, notify_user
from app.services.pricing import calculate_price
from app.services.reservations import (ACTIVE_STATUSES, describe,
                                       expire_past_pending, find_conflict,
                                       overlapping_maintenance,
                                       overlapping_reservations)

router = APIRouter(prefix="/api/reservations", tags=["Reservations"])

DAY_START_HOUR = 8
DAY_END_HOUR = 20
SLOT_HOURS = 2
WORK_DAYS = 5


def _overlaps(start, end, items) -> bool:
    return any(item.start_time < end and item.end_time > start
               for item in items)


@router.get("/availability", response_model=list[SlotOut])
def get_availability(resource_id: int, week: date,
                     user: User | None = Depends(get_optional_user),
                     db: Session = Depends(get_db)):
    if db.get(Resource, resource_id) is None:
        raise HTTPException(status_code=404, detail="Resursa nu exista")

    monday = week - timedelta(days=week.weekday())
    week_start = datetime.combine(monday, time(0, 0))
    week_end = week_start + timedelta(days=WORK_DAYS)
    reservations = overlapping_reservations(db, resource_id, week_start,
                                            week_end, ACTIVE_STATUSES)
    maintenance = overlapping_maintenance(db, resource_id,
                                          week_start, week_end)
    team_id = user.team_id if user else None
    confirmed = [r for r in reservations if r.status == "CONFIRMED"]
    team_confirmed = [r for r in confirmed
                      if team_id is not None and r.team_id == team_id]
    team_requests = [r for r in reservations
                     if r.status == "PENDING" and team_id is not None
                     and r.team_id == team_id]
    now = datetime.now()

    slots = []
    for day in range(WORK_DAYS):
        current_day = monday + timedelta(days=day)
        for hour in range(DAY_START_HOUR, DAY_END_HOUR, SLOT_HOURS):
            start = datetime.combine(current_day, time(hour, 0))
            end = start + timedelta(hours=SLOT_HOURS)
            if _overlaps(start, end, maintenance):
                status = "MAINTENANCE"
            elif _overlaps(start, end, team_confirmed):
                status = "TEAM"
            elif _overlaps(start, end, confirmed):
                status = "BOOKED"
            elif start < now:
                status = "PAST"
            elif _overlaps(start, end, team_requests):
                status = "REQUESTED"
            else:
                status = "FREE"
            slots.append(SlotOut(start_time=start, end_time=end,
                                 status=status))
    return slots


def _check_request(db: Session, data: ReservationIn, user: User) -> Resource:
    team_id = data.team_id if data.team_id is not None else user.team_id
    if team_id is None or team_id != user.team_id:
        raise HTTPException(status_code=403,
                            detail="Poti rezerva doar pentru echipa ta")
    if data.start_time < datetime.now():
        raise HTTPException(status_code=400,
                            detail="Nu poti rezerva un interval din trecut")
    resource = db.get(Resource, data.resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resursa nu exista")
    conflict = find_conflict(db, resource.id, data.start_time, data.end_time)
    if conflict:
        raise HTTPException(status_code=409, detail=conflict)
    return resource


@router.post("/quote", response_model=QuoteOut)
def quote_reservation(data: ReservationIn,
                      user: User = Depends(require_roles("LEAD")),
                      db: Session = Depends(get_db)):
    resource = _check_request(db, data, user)
    quote = calculate_price(resource.price_per_hour, data.start_time,
                            data.end_time, user.affiliation_date)
    return QuoteOut(price=quote.price, discount=quote.discount,
                    final_price=quote.final_price)


@router.post("", response_model=ReservationOut, status_code=201)
def create_reservation(data: ReservationIn,
                       user: User = Depends(require_roles("LEAD")),
                       db: Session = Depends(get_db)):
    resource = _check_request(db, data, user)
    already_requested = overlapping_reservations(
        db, resource.id, data.start_time, data.end_time, ("PENDING",))
    if any(r.team_id == user.team_id for r in already_requested):
        raise HTTPException(status_code=409,
                            detail="Echipa ta a cerut deja acest interval")

    quote = calculate_price(resource.price_per_hour, data.start_time,
                            data.end_time, user.affiliation_date)
    reservation = Reservation(
        resource_id=resource.id,
        team_id=user.team_id,
        user_id=user.id,
        start_time=data.start_time,
        end_time=data.end_time,
        price=quote.price,
        discount=quote.discount,
        final_price=quote.final_price,
        purpose=data.purpose.strip() if data.purpose else None,
        status="PENDING",
    )
    db.add(reservation)
    db.flush()
    team = db.get(Team, user.team_id)
    notify_admins(db, f"Cerere noua de rezervare de la {team.name}: "
                      f"{describe(reservation)}", reservation.id)
    db.commit()
    db.refresh(reservation)
    return reservation


def get_team_reservation(db: Session, reservation_id: int,
                         user: User) -> Reservation:
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Rezervarea nu exista")
    if user.role != "ADMIN" and reservation.team_id != user.team_id:
        raise HTTPException(status_code=403,
                            detail="Rezervarea nu apartine echipei tale")
    return reservation


def _get_pending_request(db: Session, reservation_id: int) -> Reservation:
    expire_past_pending(db)
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Rezervarea nu exista")
    if reservation.status == "EXPIRED":
        db.commit()
        raise HTTPException(status_code=410,
                            detail="Cererea a expirat, intervalul a inceput")
    if reservation.status != "PENDING":
        raise HTTPException(status_code=409,
                            detail="Cererea a primit deja un raspuns")
    return reservation


@router.post("/{reservation_id}/approve", response_model=ReservationOut)
def approve_reservation(reservation_id: int,
                        _admin: User = Depends(require_roles("ADMIN")),
                        db: Session = Depends(get_db)):
    reservation = _get_pending_request(db, reservation_id)
    conflict = find_conflict(db, reservation.resource_id,
                             reservation.start_time, reservation.end_time,
                             exclude_id=reservation.id)
    if conflict:
        raise HTTPException(status_code=409, detail=conflict)

    reservation.status = "CONFIRMED"
    notify_team(db, reservation.team_id,
                f"Rezervare aprobata: {describe(reservation)}",
                reservation.id)

    competing = overlapping_reservations(
        db, reservation.resource_id, reservation.start_time,
        reservation.end_time, ("PENDING",), exclude_id=reservation.id)
    for other in competing:
        other.status = "REJECTED"
        notify_user(db, other.user_id,
                    f"Cerere respinsa: {describe(other)} "
                    "(intervalul a fost aprobat pentru alta echipa)",
                    other.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409,
                            detail="Intervalul este deja rezervat")
    db.refresh(reservation)
    return reservation


@router.post("/{reservation_id}/reject", response_model=ReservationOut)
def reject_reservation(reservation_id: int,
                       data: RejectIn | None = None,
                       _admin: User = Depends(require_roles("ADMIN")),
                       db: Session = Depends(get_db)):
    reservation = _get_pending_request(db, reservation_id)
    reservation.status = "REJECTED"
    message = f"Cerere respinsa: {describe(reservation)}"
    if data is not None and data.reason:
        message += f" (motiv: {data.reason.strip()})"
    notify_user(db, reservation.user_id, message, reservation.id)
    db.commit()
    db.refresh(reservation)
    return reservation


@router.get("", response_model=list[ReservationOut])
def get_team_reservations(status: str | None = None,
                          resource_id: int | None = None,
                          team_id: int | None = None,
                          date_from: date | None = None,
                          date_to: date | None = None,
                          user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    expire_past_pending(db)
    db.commit()
    query = select(Reservation).order_by(Reservation.start_time.desc())
    if user.role != "ADMIN":
        if user.team_id is None:
            return []
        query = query.where(Reservation.team_id == user.team_id)
    elif team_id is not None:
        query = query.where(Reservation.team_id == team_id)
    if resource_id is not None:
        query = query.where(Reservation.resource_id == resource_id)
    if date_from is not None:
        query = query.where(
            Reservation.end_time > datetime.combine(date_from, time(0, 0)))
    if date_to is not None:
        query = query.where(Reservation.start_time < datetime.combine(
            date_to + timedelta(days=1), time(0, 0)))
    if status:
        query = query.where(Reservation.status == status.upper())
    return db.scalars(query).all()


@router.get("/{reservation_id}", response_model=ReservationOut)
def get_reservation(reservation_id: int,
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    return get_team_reservation(db, reservation_id, user)


@router.post("/{reservation_id}/cancel", response_model=ReservationOut)
def cancel_reservation(reservation_id: int,
                       data: CancelIn | None = None,
                       user: User = Depends(require_roles("LEAD", "ADMIN")),
                       db: Session = Depends(get_db)):
    reservation = get_team_reservation(db, reservation_id, user)
    if reservation.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=409,
                            detail="Rezervarea nu mai poate fi anulata")
    if reservation.start_time <= datetime.now():
        raise HTTPException(
            status_code=409,
            detail="Rezervarea a inceput deja si nu mai poate fi anulata",
        )

    was_confirmed = reservation.status == "CONFIRMED"
    by_admin = user.role == "ADMIN"
    reservation.status = "CANCELLED"
    if was_confirmed or by_admin:
        prefix = ("Rezervare anulata de administrator" if by_admin
                  else "Rezervare anulata")
        message = f"{prefix}: {describe(reservation)}"
        if data is not None and data.reason:
            message += f" (motiv: {data.reason.strip()})"
        if was_confirmed:
            notify_team(db, reservation.team_id, message, reservation.id)
        else:
            notify_user(db, reservation.user_id, message, reservation.id)
    db.commit()
    db.refresh(reservation)
    return reservation
