from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import Team, User
from app.schemas import AdminUserOut, UserOut

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    return user


def _to_admin_out(user: User, teams: dict[int, str]) -> AdminUserOut:
    data = UserOut.model_validate(user).model_dump()
    return AdminUserOut(**data, team_name=teams.get(user.team_id))


def _team_names(db: Session) -> dict[int, str]:
    return {team.id: team.name for team in db.scalars(select(Team))}


@router.get("", response_model=list[AdminUserOut])
def get_users(_admin: User = Depends(require_roles("ADMIN")),
              db: Session = Depends(get_db)):
    """Lista utilizatorilor, cu numele echipei (doar admin)."""
    teams = _team_names(db)
    users = db.scalars(select(User).order_by(User.name)).all()
    return [_to_admin_out(user, teams) for user in users]
