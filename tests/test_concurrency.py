"""Two staff members at two tills, clicking "lend" at the same moment.

Each test opens two real connections. Connection A does its work but
doesn't commit yet; connection B then tries the same thing from another
thread (it may have to wait for A's locks); then A commits.
"""
import threading

import psycopg


def add_member(conn, name, tier):
    return conn.execute(
        "INSERT INTO members (full_name, email, tier_code) VALUES (%s, %s, %s) RETURNING member_id",
        (name, f"{name.lower()}@example.com", tier),
    ).fetchone()[0]


def add_copies(conn, title, how_many):
    publisher_id = conn.execute(
        "INSERT INTO publishers (name) VALUES (%s) RETURNING publisher_id", (f"{title} publisher",)
    ).fetchone()[0]
    game_id = conn.execute(
        "INSERT INTO games (title, publisher_id) VALUES (%s, %s) RETURNING game_id", (title, publisher_id)
    ).fetchone()[0]
    return [
        conn.execute(
            "INSERT INTO copies (game_id, copy_no, shelf) VALUES (%s, %s, 'B3') RETURNING copy_id", (game_id, n)
        ).fetchone()[0]
        for n in range(1, how_many + 1)
    ]


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


def race(url, work_a, work_b):
    """A works without committing, B starts, A commits. Returns B's outcome."""
    with psycopg.connect(url) as till_a, psycopg.connect(url) as till_b:
        work_a(till_a)
        thread, outcome = run_in_background(till_b, work_b)
        thread.join(timeout=1)  # B either finishes, or is stuck waiting for A
        till_a.commit()
        thread.join()
    return outcome[0]


def count(url, query, params):
    with psycopg.connect(url) as conn:
        return conn.execute(query, params).fetchone()[0]


def test_same_copy_lent_at_the_same_time_from_two_tills(shared_db):
    with psycopg.connect(shared_db, autocommit=True) as conn:
        ana, ben = add_member(conn, "Ana", "PLUS"), add_member(conn, "Ben", "PLUS")
        [catan] = add_copies(conn, "Catan", 1)

    def insert_loan(member_id):
        return lambda conn: conn.execute("INSERT INTO loans (copy_id, member_id) VALUES (%s, %s)", (catan, member_id))

    till_b = race(shared_db, insert_loan(ana), insert_loan(ben))

    open_loans = count(shared_db, "SELECT count(*) FROM loans WHERE copy_id = %s AND returned_on IS NULL", (catan,))
    assert open_loans == 1, f"Catan is out {open_loans} times (till B: {till_b})"
    assert till_b == "UniqueViolation"


def test_member_limit_holds_when_two_tills_lend_to_the_same_member(shared_db):
    with psycopg.connect(shared_db, autocommit=True) as conn:
        cleo = add_member(conn, "Cleo", "BASIC")  # limit: 2 games
        first, second, third = add_copies(conn, "Azul", 3)
        conn.execute("SELECT lend_copy(%s, %s)", (cleo, first))  # Cleo already has 1

    def lend(copy_id):
        return lambda conn: conn.execute("SELECT lend_copy(%s, %s)", (cleo, copy_id))

    till_b = race(shared_db, lend(second), lend(third))

    open_loans = count(shared_db, "SELECT count(*) FROM loans WHERE member_id = %s AND returned_on IS NULL", (cleo,))
    assert open_loans == 2, f"Cleo has {open_loans} games on a 2-game plan (till B: {till_b})"
    assert till_b == "RaiseException"


def test_lending_to_two_different_members_does_not_wait(shared_db):
    # The member lock must not turn into a lock on the whole tier.
    with psycopg.connect(shared_db, autocommit=True) as conn:
        dana, eli = add_member(conn, "Dana", "BASIC"), add_member(conn, "Eli", "BASIC")
        first, second = add_copies(conn, "Dixit", 2)

    with psycopg.connect(shared_db) as till_a, psycopg.connect(shared_db) as till_b:
        till_a.execute("SELECT lend_copy(%s, %s)", (dana, first))
        thread, outcome = run_in_background(till_b, lambda conn: conn.execute("SELECT lend_copy(%s, %s)", (eli, second)))
        thread.join(timeout=2)
        finished_while_a_was_open = not thread.is_alive()
        till_a.commit()
        thread.join()

    assert finished_while_a_was_open
    assert outcome == ["committed"]
