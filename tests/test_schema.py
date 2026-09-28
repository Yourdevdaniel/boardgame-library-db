from datetime import date

import pytest
from psycopg import errors


def test_membership_tiers_are_seeded(conn):
    rows = conn.execute("SELECT tier_code, loan_limit, loan_days FROM membership_tiers ORDER BY tier_code").fetchall()
    assert rows == [("BASIC", 2, 7), ("PLUS", 4, 14)]


def test_email_must_be_lowercase(conn):
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "INSERT INTO members (full_name, email, tier_code) VALUES ('Maya', 'Maya@Example.com', 'PLUS')"
        )


def test_member_needs_an_existing_tier(conn):
    with pytest.raises(errors.ForeignKeyViolation):
        conn.execute("INSERT INTO members (full_name, email, tier_code) VALUES ('Maya', 'maya@example.com', 'GOLD')")


def test_copy_numbers_are_unique_per_game(conn, make_copy):
    copy_id = make_copy()
    game_id = conn.execute("SELECT game_id FROM copies WHERE copy_id = %s", (copy_id,)).fetchone()[0]
    with pytest.raises(errors.UniqueViolation):
        conn.execute("INSERT INTO copies (game_id, copy_no, shelf) VALUES (%s, 1, 'B2')", (game_id,))


def test_due_date_must_be_after_lent_date(conn, make_member, make_copy):
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "INSERT INTO loans (copy_id, member_id, lent_on, due_on) VALUES (%s, %s, %s, %s)",
            (make_copy(), make_member(), date(2026, 9, 10), date(2026, 9, 10)),
        )


def test_game_cannot_be_returned_before_it_was_lent(conn, make_member, make_copy):
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "INSERT INTO loans (copy_id, member_id, lent_on, due_on, returned_on) VALUES (%s, %s, %s, %s, %s)",
            (make_copy(), make_member(), date(2026, 9, 10), date(2026, 9, 17), date(2026, 9, 9)),
        )
