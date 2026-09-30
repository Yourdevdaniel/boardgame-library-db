from datetime import date

import pytest

from import_spreadsheet import DEFAULT_FILE, import_loans, parse_date, read_loans, to_first_normal_form

HANNAH_ROW = {
    "Date Out": "2026-08-01", "Member Name": "Hannah Weber", "Member Email": "Hannah.Weber@example.com",
    "Member Phone": "+49 151 0000 103", "Membership": "Plus", "Max Games": "4",
    "Games Taken": "Pandemic; Dixit; Splendor", "Publisher": "Z-Man Games; Libellud; Space Cowboys",
    "Copy": "1; 1; 1", "Shelf": "C2; B1; A3", "Due Back": "2026-08-15", "Returned": "2026-08-14",
}


def test_parse_date_accepts_both_formats_in_the_sheet():
    assert parse_date("2026-07-03") == date(2026, 7, 3)
    assert parse_date("03/07/2026") == date(2026, 7, 3)  # day first


def test_parse_date_rejects_anything_else():
    with pytest.raises(ValueError):
        parse_date("July 3rd")


def test_multi_game_row_becomes_one_loan_per_copy():
    loans = list(to_first_normal_form(HANNAH_ROW))
    assert [(l["title"], l["publisher"], l["shelf"]) for l in loans] == [
        ("Pandemic", "Z-Man Games", "C2"),
        ("Dixit", "Libellud", "B1"),
        ("Splendor", "Space Cowboys", "A3"),
    ]
    assert all(l["email"] == "hannah.weber@example.com" for l in loans)


def test_row_whose_lists_do_not_line_up_is_rejected():
    row = dict(HANNAH_ROW, Copy="1; 1")
    with pytest.raises(ValueError):
        list(to_first_normal_form(row))


def test_importing_the_real_spreadsheet(conn):
    warnings = import_loans(conn, read_loans(DEFAULT_FILE))

    counts = conn.execute(
        """
        SELECT (SELECT count(*) FROM members), (SELECT count(*) FROM games),
               (SELECT count(*) FROM copies),  (SELECT count(*) FROM loans),
               (SELECT count(*) FROM loans WHERE returned_on IS NULL)
        """
    ).fetchone()
    assert counts == (8, 10, 12, 42, 7)

    titles = [t for (t,) in conn.execute("SELECT title FROM games ORDER BY title")]
    assert "Catan" in titles and "catan" not in titles
    assert "Ticket to Ride" in titles and "Ticket To Ride" not in titles

    assert any("912000102" in w for w in warnings)
    assert any("Priya Nair" in w and "BASIC allows 2" in w for w in warnings)
    assert sum("return date missing" in w for w in warnings) == 2
