"""One-time helper: create the app user and database in local PostgreSQL.

Run from backend/ with the venv active:
    python scripts/create_db.py
Passwords are typed at the prompt and are never stored.
"""
import getpass

# pyrefly: ignore [missing-import]
import psycopg
# pyrefly: ignore [missing-import]
from psycopg import sql

host = input("Host [localhost]: ").strip() or "localhost"
port = int(input("Port [5432]: ").strip() or "5432")
admin_user = input("Admin user [postgres]: ").strip() or "postgres"
admin_password = getpass.getpass("Admin (postgres) password: ")
app_user = input("App user to create [hiring_user]: ").strip() or "hiring_user"
app_password = getpass.getpass("Password for the app user (letters and digits only): ")
db_name = input("Database name [hiring_agent]: ").strip() or "hiring_agent"

with psycopg.connect(
    host=host,
    port=port,
    user=admin_user,
    password=admin_password,
    dbname="postgres",
    autocommit=True,
) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app_user,))
        if cur.fetchone():
            cur.execute(
                sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(app_user), sql.Literal(app_password)
                )
            )
            print(f"Role '{app_user}' already existed: password updated.")
        else:
            cur.execute(
                sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(app_user), sql.Literal(app_password)
                )
            )
            print(f"Role '{app_user}' created.")

        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if cur.fetchone():
            cur.execute(
                sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                    sql.Identifier(db_name), sql.Identifier(app_user)
                )
            )
            print(f"Database '{db_name}' already existed: owner set to '{app_user}'.")
        else:
            cur.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(db_name), sql.Identifier(app_user)
                )
            )
            print(f"Database '{db_name}' created.")

print("\nDone. Put this in backend/.env (replace Yash1234):")
print(f"DATABASE_URL=postgresql+psycopg://hiring_user:Yash1234@localhost:5432/hiring_agent")