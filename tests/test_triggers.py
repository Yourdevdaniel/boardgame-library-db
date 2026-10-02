from datetime import date, timedelta

import pytest

LENT_ON = date(2026, 9, 1)


def lend(conn, copy_id, member_id, due_on=None):
    return conn.execute(
        "INSERT INTO loans (copy_id, member_id, lent_on, due_on) VALUES (%s, %s, %s, %s) RETURNING loan_id, due_on",
        (copy_id, member_id, LENT_ON, due_on),
    ).fetchone()


@pytest.mark.parametrize("tier, days", [("BASIC", 7), ("PLUS", 14)])
def test_due_date_comes_from_the_members_tier(conn, make_member, make_copy, tier, days):
    _, due_on = lend(conn, make_copy(), make_member(tier))
    assert due_on == LENT_ON + timedelta(days=days)


def test_explicit_due_date_is_kept(conn, make_member, make_copy):
    _, due_on = lend(conn, make_copy(), make_member(), due_on=date(2026, 9, 3))
    assert due_on == date(2026, 9, 3)


def test_copy_can_be_lent_again_after_it_is_returned(conn, make_member, make_copy):
    copy_id = make_copy()
    loan_id, _ = lend(conn, copy_id, make_member())
    conn.execute("UPDATE loans SET returned_on = %s WHERE loan_id = %s", (LENT_ON + timedelta(days=2), loan_id))
    lend(conn, copy_id, make_member())  # no exception


def test_lending_and_returning_are_logged(conn, make_member, make_copy):
    loan_id, _ = lend(conn, make_copy(), make_member())
    conn.execute("UPDATE loans SET due_on = due_on + 1 WHERE loan_id = %s", (loan_id,))  # not a return
    conn.execute("UPDATE loans SET returned_on = %s WHERE loan_id = %s", (LENT_ON + timedelta(days=3), loan_id))

    events = conn.execute("SELECT event FROM loan_events WHERE loan_id = %s ORDER BY event_id", (loan_id,)).fetchall()
    assert events == [("LENT",), ("RETURNED",)]
