"""Import the café's old loan spreadsheet into the normalized tables.

Usage:  python import_spreadsheet.py [path/to/file.csv]

Run it on a freshly built database (python db.py). The whole import is one
transaction: if the database rejects any row, nothing is imported, so the
spreadsheet can be fixed and the import simply run again.
"""
import csv
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import psycopg

import db

DEFAULT_FILE = Path(__file__).resolve().parent / "data" / "cafe_loans_spreadsheet.csv"

# The sheet mixes ISO dates with day-first dates. Rows like 14/07/2026 prove
# the second format is DD/MM, not the US MM/DD.
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")


def parse_date(text):
    text = text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date: {text!r}")


def split_list(cell):
    return [part.strip() for part in cell.split(";")]


def to_first_normal_form(row):
    """Turn one spreadsheet row into one dict per borrowed copy."""
    games = split_list(row["Games Taken"])
    publishers = split_list(row["Publisher"])
    copy_numbers = split_list(row["Copy"])
    shelves = split_list(row["Shelf"])
    if not len(games) == len(publishers) == len(copy_numbers) == len(shelves):
        raise ValueError(f"list columns don't line up: {row['Games Taken']!r} / {row['Copy']!r}")

    for game, publisher, copy_no, shelf in zip(games, publishers, copy_numbers, shelves):
        yield {
            "email": row["Member Email"].strip().lower(),
            "name": row["Member Name"].strip(),
            "phone": row["Member Phone"].strip(),
            "tier": row["Membership"].strip().upper(),
            "max_games": int(row["Max Games"]),
            "title": " ".join(game.split()),  # also collapses double spaces
            "publisher": publisher,
            "copy_no": int(copy_no),
            "shelf": shelf,
            "lent_on": parse_date(row["Date Out"]),
            "due_on": parse_date(row["Due Back"]),
            "returned": row["Returned"].strip(),
        }


def read_loans(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [loan for row in csv.DictReader(f) for loan in to_first_normal_form(row)]


def most_common(values):
    """The value typed most often wins; ties go to the one seen first."""
    return Counter(values).most_common(1)[0][0]


def import_loans(conn, loans):
    """Insert the loans (already in 1NF) and everything they refer to.

    Returns a list of warnings about data that had to be guessed or cleaned.
    """
    warnings = []

    # "Catan" and "catan" are the same game.
    spellings = defaultdict(list)
    for loan in loans:
        spellings[loan["title"].casefold()].append(loan["title"])
    title_of = {}
    for key, names in spellings.items():
        title_of[key] = most_common(names)
        if len(set(names)) > 1:
            warnings.append(f"title written as {sorted(set(names))}, using {title_of[key]!r}")
    for loan in loans:
        loan["title"] = title_of[loan["title"].casefold()]

    member_ids = insert_members(conn, loans, warnings)
    copy_ids = insert_games_and_copies(conn, loans)

    for loan in loans:
        if loan["returned"] == "":
            returned_on = None
        elif loan["returned"].lower() == "yes":
            # Returned, but nobody wrote down when. The due date is the best
            # guess we have; the warning makes sure it isn't silently wrong.
            returned_on = loan["due_on"]
            warnings.append(f"{loan['title']} lent on {loan['lent_on']}: return date missing, using due date")
        else:
            returned_on = parse_date(loan["returned"])

        conn.execute(
            """
            INSERT INTO loans (copy_id, member_id, lent_on, due_on, returned_on)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (copy_ids[loan["title"], loan["copy_no"]], member_ids[loan["email"]],
             loan["lent_on"], loan["due_on"], returned_on),
        )
    return warnings


def insert_members(conn, loans, warnings):
    rows_by_email = defaultdict(list)
    for loan in loans:
        rows_by_email[loan["email"]].append(loan)
    tier_limits = dict(conn.execute("SELECT tier_code, loan_limit FROM membership_tiers").fetchall())

    member_ids = {}
    for email, rows in rows_by_email.items():
        name = most_common(r["name"] for r in rows)
        tier = most_common(r["tier"] for r in rows)
        phones = [r["phone"] for r in rows]
        phone = most_common(phones)
        if len(set(phones)) > 1:
            warnings.append(f"{name}: phone written as {sorted(set(phones))}, using {phone!r}")
        wrong_limits = {r["max_games"] for r in rows} - {tier_limits[tier]}
        if wrong_limits:
            warnings.append(
                f"{name}: 'Max Games' says {sorted(wrong_limits)} but {tier} allows {tier_limits[tier]}; "
                "the tier table decides now"
            )
        member_ids[email] = conn.execute(
            "INSERT INTO members (full_name, email, phone, tier_code) VALUES (%s, %s, %s, %s) RETURNING member_id",
            (name, email, phone, tier),
        ).fetchone()[0]
    return member_ids


def insert_games_and_copies(conn, loans):
    publishers_by_title = defaultdict(list)
    shelves_by_copy = defaultdict(list)
    for loan in loans:
        publishers_by_title[loan["title"]].append(loan["publisher"])
        shelves_by_copy[loan["title"], loan["copy_no"]].append(loan["shelf"])

    publisher_ids = {}
    game_ids = {}
    for title, names in publishers_by_title.items():
        publisher = most_common(names)
        if publisher not in publisher_ids:
            publisher_ids[publisher] = conn.execute(
                "INSERT INTO publishers (name) VALUES (%s) RETURNING publisher_id", (publisher,)
            ).fetchone()[0]
        game_ids[title] = conn.execute(
            "INSERT INTO games (title, publisher_id) VALUES (%s, %s) RETURNING game_id",
            (title, publisher_ids[publisher]),
        ).fetchone()[0]

    copy_ids = {}
    for (title, copy_no), shelves in shelves_by_copy.items():
        copy_ids[title, copy_no] = conn.execute(
            "INSERT INTO copies (game_id, copy_no, shelf) VALUES (%s, %s, %s) RETURNING copy_id",
            (game_ids[title], copy_no, most_common(shelves)),
        ).fetchone()[0]
    return copy_ids


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FILE
    loans = read_loans(path)
    with psycopg.connect(db.database_url()) as conn:
        warnings = import_loans(conn, loans)
    for warning in warnings:
        print("warning:", warning)
    print(f"Imported {len(loans)} loans from {path.name}.")


if __name__ == "__main__":
    main()
