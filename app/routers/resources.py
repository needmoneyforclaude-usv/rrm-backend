import base64
import binascii
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Category, Maintenance, Reservation, Resource
from app.schemas import CategoryOut, ImageUpload, ResourceIn, ResourceOut

router = APIRouter(prefix="/api", tags=["Resources"])

IMAGES_DIR = Path(__file__).resolve().parents[2] / "static" / "images"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _check_category(db: Session, category_id: int | None):
    if category_id is not None and db.get(Category, category_id) is None:
        raise HTTPException(status_code=400, detail="Categoria nu exista")


@router.get("/categories", response_model=list[CategoryOut])
def get_categories(db: Session = Depends(get_db)):
    return db.scalars(select(Category).order_by(Category.id)).all()


@router.get("/resources", response_model=list[ResourceOut])
def get_resources(category_id: int | None = None,
                  db: Session = Depends(get_db)):
    query = select(Resource).order_by(Resource.id)
    if category_id is not None:
        query = query.where(Resource.category_id == category_id)
    resources = db.scalars(query).all()

    now = datetime.now()
    in_maintenance = set(db.scalars(
        select(Maintenance.resource_id).where(Maintenance.start_time <= now,
                                              Maintenance.end_time > now)
    ))
    return [ResourceOut.model_validate(r).model_copy(
        update={"in_maintenance": r.id in in_maintenance}) for r in resources]


@router.get("/resources/{resource_id}", response_model=ResourceOut)
def get_resource(resource_id: int, db: Session = Depends(get_db)):
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resursa nu exista")
    return resource


@router.post("/resources", response_model=ResourceOut, status_code=201)
def create_resource(data: ResourceIn,
                    _admin=Depends(require_roles("ADMIN")),
                    db: Session = Depends(get_db)):
    _check_category(db, data.category_id)
    resource = Resource(**data.model_dump())
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


@router.put("/resources/{resource_id}", response_model=ResourceOut)
def update_resource(resource_id: int, data: ResourceIn,
                    _admin=Depends(require_roles("ADMIN")),
                    db: Session = Depends(get_db)):
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resursa nu exista")
    _check_category(db, data.category_id)
    for key, value in data.model_dump().items():
        setattr(resource, key, value)
    db.commit()
    db.refresh(resource)
    return resource


@router.delete("/resources/{resource_id}", status_code=204)
def delete_resource(resource_id: int,
                    _admin=Depends(require_roles("ADMIN")),
                    db: Session = Depends(get_db)):
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resursa nu exista")
    # rezervarile raman ca istoric pentru echipe, deci nu le stergem
    has_reservations = db.scalar(
        select(Reservation.id).where(Reservation.resource_id == resource_id)
        .limit(1)
    )
    if has_reservations is not None:
        raise HTTPException(
            status_code=409,
            detail="Resursa are rezervari si nu poate fi stearsa",
        )
    db.execute(delete(Maintenance).where(
        Maintenance.resource_id == resource_id))
    db.delete(resource)
    db.commit()


@router.post("/resources/{resource_id}/image", response_model=ResourceOut)
def upload_resource_image(resource_id: int, data: ImageUpload,
                          _admin=Depends(require_roles("ADMIN")),
                          db: Session = Depends(get_db)):
    """Salveaza poza resursei (trimisa ca base64) in static/images."""
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resursa nu exista")
    extension = Path(data.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400,
                            detail="Imaginea trebuie sa fie jpg, png sau webp")
    try:
        content = base64.b64decode(data.content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Imagine invalida")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400,
                            detail="Imaginea poate avea maxim 5 MB")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    # timestamp in nume ca browserul sa nu tina minte poza veche
    name = f"resource-{resource.id}-{int(time.time())}{extension}"
    (IMAGES_DIR / name).write_bytes(content)
    resource.image_url = f"/static/images/{name}"
    db.commit()
    db.refresh(resource)
    return resource
