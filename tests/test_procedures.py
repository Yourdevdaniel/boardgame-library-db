from datetime import date, timedelta

import pytest
from psycopg import errors

TODAY = date.today()


def lend(conn, member_id, copy_id):
    return conn.execute("SELECT lend_copy(%s, %s)", (member_id, copy_id)).fetchone()[0]


def test_lend_copy_returns_the_new_loan(conn, make_member, make_copy):
    member_id, copy_id = make_member("PLUS"), make_copy()
    loan_id = lend(conn, member_id, copy_id)

    row = conn.execute("SELECT member_id, copy_id, lent_on, due_on FROM loans WHERE loan_id = %s", (loan_id,)).fetchone()
    assert row == (member_id, copy_id, TODAY, TODAY + timedelta(days=14))


def test_basic_member_cannot_take_a_third_game(conn, make_member, make_copy):
    member_id = make_member("BASIC")
    lend(conn, member_id, make_copy())
    lend(conn, member_id, make_copy())
    with pytest.raises(errors.RaiseException, match="already has 2 of 2 games"):
        lend(conn, member_id, make_copy())


def test_plus_member_can_take_four_games(conn, make_member, make_copy):
    member_id = make_member("PLUS")
    for _ in range(4):
        lend(conn, member_id, make_copy())
    with pytest.raises(errors.RaiseException, match="already has 4 of 4 games"):
        lend(conn, member_id, make_copy())


def test_member_with_an_overdue_game_cannot_borrow(conn, make_member, make_copy):
    member_id = make_member("PLUS")
    conn.execute(
        "INSERT INTO loans (copy_id, member_id, lent_on, due_on) VALUES (%s, %s, %s, %s)",
        (make_copy(), member_id, TODAY - timedelta(days=20), TODAY - timedelta(days=6)),
    )
    with pytest.raises(errors.RaiseException, match="overdue"):
        lend(conn, member_id, make_copy())


def test_lending_a_copy_that_is_out_gives_a_readable_error(conn, make_member, make_copy):
    copy_id = make_copy()
    lend(conn, make_member(), copy_id)
    with pytest.raises(errors.RaiseException, match="already lent out"):
        lend(conn, make_member(), copy_id)


def test_unknown_member(conn, make_copy):
    with pytest.raises(errors.RaiseException, match="does not exist"):
        lend(conn, 999_999, make_copy())


def test_return_copy_closes_the_loan_and_frees_the_copy(conn, make_member, make_copy):
    copy_id = make_copy()
    loan_id = lend(conn, make_member(), copy_id)

    conn.execute("CALL return_copy(%s)", (loan_id,))

    assert conn.execute("SELECT returned_on FROM loans WHERE loan_id = %s", (loan_id,)).fetchone()[0] == TODAY
    lend(conn, make_member(), copy_id)  # the copy is available again


def test_a_loan_cannot_be_returned_twice(conn, make_member, make_copy):
    loan_id = lend(conn, make_member(), make_copy())
    conn.execute("CALL return_copy(%s)", (loan_id,))
    with pytest.raises(errors.RaiseException, match="already returned"):
        conn.execute("CALL return_copy(%s)", (loan_id,))
