"""Connection and setup helpers shared by the scripts and the tests.

The database comes from the DATABASE_URL environment variable, for example:

    DATABASE_URL=postgresql://postgres@localhost:5432/boardgame_library

Run `python db.py` to drop, re-create and build the database from sql/.
"""
import os
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

SQL_DIR = Path(__file__).resolve().parent / "sql"
DEFAULT_URL = "postgresql://postgres@localhost:5432/boardgame_library"


def database_url():
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def recreate_database(url):
    """Drop and create the database named in `url`.

    You can't drop the database you are connected to, so this connects to
    the default 'postgres' database on the same server to do it.
    """
    params = conninfo_to_dict(url)
    name = params["dbname"]
    params["dbname"] = "postgres"
    with psycopg.connect(make_conninfo(**params), autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def apply_schema(url):
    """Run every file in sql/ in name order.

    All files run in one transaction, so if one of them fails the database
    is left empty instead of half-built.
    """
    with psycopg.connect(url) as conn:
        for path in sorted(SQL_DIR.glob("*.sql")):
            conn.execute(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    url = database_url()
    recreate_database(url)
    apply_schema(url)
    print(f"Built {conninfo_to_dict(url)['dbname']} from {len(list(SQL_DIR.glob('*.sql')))} SQL files.")
