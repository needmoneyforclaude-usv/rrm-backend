import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def already_has_test_resources(conn) -> bool:
    return conn.execute(text(
        "SELECT 1 FROM categories WHERE name = 'Laboratoare'")).first() is not None


def main():
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "name VARCHAR(255) PRIMARY KEY, "
            "applied_at TIMESTAMP NOT NULL DEFAULT NOW())"))
        applied = set(conn.execute(
            text("SELECT name FROM schema_migrations")).scalars())

    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            continue
        try:
            with engine.begin() as conn:
                if (path.name.startswith("001")
                        and already_has_test_resources(conn)):
                    print(f"skip  {path.name} (datele exista deja)")
                else:
                    conn.exec_driver_sql(path.read_text(encoding="utf-8"))
                    print(f"ok    {path.name}")
                conn.execute(text("INSERT INTO schema_migrations (name) "
                                  "VALUES (:name)"), {"name": path.name})
        except Exception as error:
            print(f"EROARE {path.name}: {str(error).splitlines()[0]}")
    print("Baza de date e la zi.")


if __name__ == "__main__":
    main()
