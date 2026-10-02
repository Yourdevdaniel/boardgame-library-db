"""Two staff members at two tills, clicking "lend" at the same moment.

Each test opens two real connections. Connection A does its work but
doesn't commit yet; connection B then tries the same thing from another
thread (it may have to wait for A's locks); then A commits.
"""
import threading

import psycopg


def setup_rows(url):
    with psycopg.connect(url, autocommit=True) as conn:
        member_a, member_b = [
            conn.execute(
                "INSERT INTO members (full_name, email, tier_code) VALUES (%s, %s, 'PLUS') RETURNING member_id",
                (name, f"{name.lower()}@example.com"),
            ).fetchone()[0]
            for name in ("Ana", "Ben")
        ]
        publisher_id = conn.execute("INSERT INTO publishers (name) VALUES ('Kosmos') RETURNING publisher_id").fetchone()[0]
        game_id = conn.execute(
            "INSERT INTO games (title, publisher_id) VALUES ('Catan', %s) RETURNING game_id", (publisher_id,)
        ).fetchone()[0]
        copy_id = conn.execute(
            "INSERT INTO copies (game_id, copy_no, shelf) VALUES (%s, 1, 'B3') RETURNING copy_id", (game_id,)
        ).fetchone()[0]
    return member_a, member_b, copy_id


def lend(conn, copy_id, member_id):
    conn.execute("INSERT INTO loans (copy_id, member_id) VALUES (%s, %s)", (copy_id, member_id))


def run_in_background(conn, work):
    """Run work(conn) + commit in a thread; returns (thread, outcome list)."""
    outcome = []

    def target():
        try:
            work(conn)
            conn.commit()
            outcome.append("committed")
        except psycopg.Error as e:
            conn.rollback()
            outcome.append(type(e).__name__)

    thread = threading.Thread(target=target)
    thread.start()
    return thread, outcome


def test_same_copy_lent_at_the_same_time_from_two_tills(shared_db):
    ana, ben, catan = setup_rows(shared_db)

    with psycopg.connect(shared_db) as till_a, psycopg.connect(shared_db) as till_b:
        lend(till_a, catan, ana)  # not committed yet

        thread, outcome = run_in_background(till_b, lambda conn: lend(conn, catan, ben))
        thread.join(timeout=1)  # B either finishes, or is stuck waiting for A
        till_a.commit()
        thread.join()

    with psycopg.connect(shared_db) as conn:
        open_loans = conn.execute(
            "SELECT count(*) FROM loans WHERE copy_id = %s AND returned_on IS NULL", (catan,)
        ).fetchone()[0]
    assert open_loans == 1, f"Catan is out {open_loans} times (till B: {outcome[0]})"
    assert outcome == ["UniqueViolation"]
