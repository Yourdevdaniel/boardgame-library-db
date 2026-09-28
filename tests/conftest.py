import itertools
import os

import psycopg
import pytest

import db

TEST_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres@localhost:5432/boardgame_library_test",
)


@pytest.fixture(scope="session")
def db_url():
    """Build a fresh test database once per test run."""
    db.recreate_database(TEST_URL)
    db.apply_schema(TEST_URL)
    return TEST_URL


@pytest.fixture
def conn(db_url):
    """A connection whose changes are rolled back after each test."""
    with psycopg.connect(db_url) as connection:
        yield connection
        connection.rollback()


@pytest.fixture
def make_member(conn):
    numbers = itertools.count(1)

    def make(tier="BASIC"):
        n = next(numbers)
        return conn.execute(
            "INSERT INTO members (full_name, email, tier_code) VALUES (%s, %s, %s) RETURNING member_id",
            (f"Member {n}", f"member{n}@example.com", tier),
        ).fetchone()[0]

    return make


@pytest.fixture
def make_copy(conn):
    """Creates a new game (and publisher) with one copy; returns copy_id."""
    numbers = itertools.count(1)

    def make():
        n = next(numbers)
        publisher_id = conn.execute(
            "INSERT INTO publishers (name) VALUES (%s) RETURNING publisher_id", (f"Publisher {n}",)
        ).fetchone()[0]
        game_id = conn.execute(
            "INSERT INTO games (title, publisher_id) VALUES (%s, %s) RETURNING game_id", (f"Game {n}", publisher_id)
        ).fetchone()[0]
        return conn.execute(
            "INSERT INTO copies (game_id, copy_no, shelf) VALUES (%s, 1, 'A1') RETURNING copy_id", (game_id,)
        ).fetchone()[0]

    return make
