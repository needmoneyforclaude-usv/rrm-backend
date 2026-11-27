# rrm-backend

Backend for Research Resource Manager. FastAPI + PostgreSQL.

Frontend: https://github.com/needmoneyforclaude-usv/rrm-frontend

## Requirements

- Python 3.12+
- PostgreSQL 15+

## Setup

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set `DATABASE_URL` to your local database (user, password, database name).

## Database

Create the database in pgAdmin or psql, then run:

```
python db\migrate.py
```

Migrations are also applied automatically when the server starts.

## Run

```
uvicorn app.main:app --reload
```

API runs on http://localhost:8000, Swagger docs on http://localhost:8000/docs.

## Tests

```
pytest
```
