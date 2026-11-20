import runpy
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (auth, maintenance, notifications, reservations,
                         resources, statistics, teams, users)

MIGRATE_SCRIPT = Path(__file__).resolve().parent.parent / "db" / "migrate.py"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # la pornire se aplica migrarile care lipsesc din baza de date
    runpy.run_path(str(MIGRATE_SCRIPT), run_name="__main__")
    yield


app = FastAPI(title="Research Resource Manager API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(teams.router)
app.include_router(resources.router)
app.include_router(reservations.router)
app.include_router(maintenance.router)
app.include_router(maintenance.periods_router)
app.include_router(notifications.router)
app.include_router(statistics.router)


@app.get("/")
def root():
    return {"status": "ok"}
