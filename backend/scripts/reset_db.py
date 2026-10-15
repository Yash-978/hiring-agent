"""Development-only database reset script.

Drops and recreates all tables on local development database.
"""
import sys
from pathlib import Path

# Ensure backend root is in sys.path when script is executed directly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# pyrefly: ignore [missing-import]
from sqlalchemy.engine import make_url
# pyrefly: ignore [missing-import]
from sqlmodel import SQLModel

from app.config import get_settings
from app.db import engine
import app.models  # noqa: F401 - ensure all tables are registered on SQLModel.metadata


def reset_db() -> None:
    settings = get_settings()
    url = make_url(settings.DATABASE_URL)

    if url.host not in ("localhost", "127.0.0.1"):
        print(
            f"Refusing to run: DATABASE_URL host is '{url.host}', "
            "but must be 'localhost' or '127.0.0.1'."
        )
        sys.exit(1)

    print(
        f"WARNING: This will drop ALL tables and recreate them in "
        f"'{url.database}' on {url.host}:{url.port}."
    )
    confirmation = input("Type 'RESET' to continue: ").strip()
    if confirmation != "RESET":
        print("Aborted.")
        sys.exit(1)

    print("Dropping all tables...")
    SQLModel.metadata.drop_all(engine)
    print("Creating all tables...")
    SQLModel.metadata.create_all(engine)
    print("Database reset successfully.")


if __name__ == "__main__":
    reset_db()
