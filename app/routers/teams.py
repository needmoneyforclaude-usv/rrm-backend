from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Team
from app.schemas import TeamOut

router = APIRouter(prefix="/api/teams", tags=["Teams"])


@router.get("", response_model=list[TeamOut])
def get_teams(db: Session = Depends(get_db)):
    """Lista echipelor, folosita la sign up."""
    return db.scalars(select(Team).order_by(Team.name)).all()
