"""Check which .env and which database the backend will really use."""
import os

from dotenv import find_dotenv, load_dotenv
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine, text
# pyrefly: ignore [missing-import]
from sqlalchemy.engine import make_url

path = find_dotenv(usecwd=True)
print("env file used :", path or "NONE FOUND")
load_dotenv(path, override=True)

url = make_url(os.environ["DATABASE_URL"])
print("driver        :", url.drivername)
print("host:port/db  :", f"{url.host}:{url.port}/{url.database}")

with create_engine(url).connect() as conn:
    print("server        :", conn.execute(text("select version()")).scalar())
    conn.execute(text("create table if not exists _perm_check (id int)"))
    conn.execute(text("drop table _perm_check"))
    conn.commit()
    print("create tables : OK") 