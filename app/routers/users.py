from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import Team, User
from app.schemas import AdminUserOut, UserOut, UserUpdate

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


@router.put("/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, data: UserUpdate,
                admin: User = Depends(require_roles("ADMIN")),
                db: Session = Depends(get_db)):
    """Adminul schimba rolul, echipa si data afilierii unui utilizator.

    Se trimit doar campurile care se schimba. Regulile:
    - adminul nu are echipa, MEMBER si LEAD trebuie sa aiba una;
    - o echipa are un singur Team Lead (teams.lead_id);
    - adminul nu isi poate scoate singur rolul de admin.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404,
                            detail="Utilizatorul nu exista")

    sent = data.model_fields_set
    role = data.role if "role" in sent else user.role
    team_id = data.team_id if "team_id" in sent else user.team_id

    if user.id == admin.id and role != "ADMIN":
        raise HTTPException(status_code=400,
                            detail="Nu iti poti scoate singur rolul de admin")
    if role == "ADMIN":
        team_id = None
    elif team_id is None:
        raise HTTPException(status_code=400,
                            detail="Membrii si Team Lead-ii trebuie sa "
                                   "aiba o echipa")

    new_team = db.get(Team, team_id) if team_id is not None else None
    if team_id is not None and new_team is None:
        raise HTTPException(status_code=400, detail="Echipa nu exista")
    if (role == "LEAD" and new_team.lead_id is not None
            and new_team.lead_id != user.id):
        raise HTTPException(status_code=409,
                            detail="Echipa are deja un Team Lead")

    # daca userul era lead, echipa veche ramane fara lead
    for team in db.scalars(select(Team).where(Team.lead_id == user.id)):
        if role != "LEAD" or team.id != team_id:
            team.lead_id = None
    if role == "LEAD":
        new_team.lead_id = user.id

    user.role = role
    user.team_id = team_id
    if "affiliation_date" in sent and data.affiliation_date is not None:
        user.affiliation_date = data.affiliation_date
    db.commit()
    db.refresh(user)
    return _to_admin_out(user, _team_names(db))
