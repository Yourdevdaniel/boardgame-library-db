from datetime import date, timedelta

TODAY = date.today()


def lend(conn, copy_id, member_id, lent_on, due_on, returned_on=None):
    conn.execute(
        "INSERT INTO loans (copy_id, member_id, lent_on, due_on, returned_on) VALUES (%s, %s, %s, %s, %s)",
        (copy_id, member_id, lent_on, due_on, returned_on),
    )


def test_overdue_loans_lists_only_open_loans_past_their_due_date(conn, make_member, make_copy):
    member = make_member()
    late, on_time, returned_late = make_copy(), make_copy(), make_copy()
    lend(conn, late, member, TODAY - timedelta(days=10), TODAY - timedelta(days=3))
    lend(conn, on_time, member, TODAY - timedelta(days=2), TODAY + timedelta(days=5))
    lend(conn, returned_late, member, TODAY - timedelta(days=20), TODAY - timedelta(days=13),
         returned_on=TODAY - timedelta(days=1))

    rows = conn.execute("SELECT title, days_overdue FROM overdue_loans").fetchall()
    late_title = conn.execute(
        "SELECT title FROM games JOIN copies USING (game_id) WHERE copy_id = %s", (late,)
    ).fetchone()[0]
    assert rows == [(late_title, 3)]


def test_loan_due_today_is_not_overdue_yet(conn, make_member, make_copy):
    lend(conn, make_copy(), make_member(), TODAY - timedelta(days=7), TODAY)
    assert conn.execute("SELECT count(*) FROM overdue_loans").fetchone()[0] == 0


def test_available_copies_hides_copies_that_are_out(conn, make_member, make_copy):
    out, returned, never_lent = make_copy(), make_copy(), make_copy()
    member = make_member()
    lend(conn, out, member, TODAY, TODAY + timedelta(days=7))
    lend(conn, returned, member, TODAY - timedelta(days=9), TODAY - timedelta(days=2), TODAY - timedelta(days=3))

    available = {c for (c,) in conn.execute("SELECT copy_id FROM available_copies")}
    assert out not in available
    assert {returned, never_lent} <= available


def test_game_popularity_counts_games_that_were_never_lent(conn, make_member, make_copy):
    popular, unpopular = make_copy(), make_copy()
    member = make_member()
    lend(conn, popular, member, TODAY - timedelta(days=30), TODAY - timedelta(days=23), TODAY - timedelta(days=24))
    lend(conn, popular, member, TODAY - timedelta(days=2), TODAY + timedelta(days=5))

    stats = {
        copy_id: conn.execute(
            """
            SELECT copies_owned, times_lent, out_now FROM game_popularity p
            JOIN games g ON g.title = p.title JOIN copies c ON c.game_id = g.game_id
            WHERE c.copy_id = %s
            """,
            (copy_id,),
        ).fetchone()
        for copy_id in (popular, unpopular)
    }
    assert stats[popular] == (1, 2, 1)
    assert stats[unpopular] == (1, 0, 0)
