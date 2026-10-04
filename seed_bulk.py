"""Fill a fresh database with three years of made-up activity.

42 imported loans are not enough to see how the queries behave, so this
generates about half a million. Everything is done in SQL with
generate_series; building the rows in Python and sending them one by one
would take minutes instead of seconds.

Usage:  python db.py && python seed_bulk.py
"""
import time

import psycopg

import db

SEED = """
SELECT setseed(0.42);  -- same "random" data on every run

INSERT INTO publishers (name)
SELECT 'Publisher ' || n FROM generate_series(1, 300) AS n;

INSERT INTO games (title, publisher_id)
SELECT 'Game ' || n, 1 + n % 300 FROM generate_series(1, 1500) AS n;

-- Every game has copy 1; every 2nd game also has copy 2, every 3rd copy 3.
INSERT INTO copies (game_id, copy_no, shelf)
SELECT g, c, chr(65 + g % 8) || (1 + g % 5)
FROM generate_series(1, 1500) AS g, generate_series(1, 3) AS c
WHERE g % c = 0;

INSERT INTO members (full_name, email, tier_code)
SELECT 'Member ' || n, 'member' || n || '@example.com',
       CASE WHEN n % 4 = 0 THEN 'PLUS' ELSE 'BASIC' END
FROM generate_series(1, 20000) AS n;

-- The history table is for real activity, not generated rows.
ALTER TABLE loans DISABLE TRIGGER loans_log_event;

-- Returned loans spread over the last three years.
INSERT INTO loans (copy_id, member_id, lent_on, due_on, returned_on)
SELECT copy_id, member_id, lent_on, lent_on + 7, lent_on + 1 + (random() * 8)::int
FROM (
    SELECT 1 + (random() * (SELECT count(*) - 1 FROM copies))::int AS copy_id,
           1 + (random() * 19999)::int                           AS member_id,
           current_date - 30 - (random() * 1065)::int             AS lent_on
    FROM generate_series(1, 500000)
) AS generated;

-- About 5% of copies are out right now; some of them are overdue.
INSERT INTO loans (copy_id, member_id, lent_on, due_on)
SELECT copy_id, 1 + (random() * 19999)::int, lent_on, lent_on + 7
FROM (
    SELECT copy_id, current_date - (random() * 20)::int AS lent_on
    FROM copies
    WHERE random() < 0.05
) AS out_now;

ALTER TABLE loans ENABLE TRIGGER loans_log_event;
"""


def main():
    started = time.perf_counter()
    with psycopg.connect(db.database_url()) as conn:
        if conn.execute("SELECT count(*) FROM loans").fetchone()[0]:
            raise SystemExit("seed_bulk.py expects an empty database: run `python db.py` first")
        conn.execute(SEED)
        counts = conn.execute(
            "SELECT (SELECT count(*) FROM members), (SELECT count(*) FROM copies), (SELECT count(*) FROM loans)"
        ).fetchone()
    with psycopg.connect(db.database_url(), autocommit=True) as conn:
        conn.execute("ANALYZE")  # fresh statistics, or the planner guesses row counts
    print(f"{counts[0]} members, {counts[1]} copies, {counts[2]} loans in {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
