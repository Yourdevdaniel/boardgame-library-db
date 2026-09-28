# boardgame-library-db

A PostgreSQL database for the lending shelf of a (fictional) board-game café,
*Meeple & Mug*.

Members can take games home for a few days. Until now the staff tracked every
loan in one shared spreadsheet ([`data/cafe_loans_spreadsheet.csv`](data/cafe_loans_spreadsheet.csv)).
It mostly worked, but:

- the same member's phone number is typed differently in different rows,
- one cell sometimes holds three games at once (`Pandemic; Dixit; Splendor`),
- dates are a mix of `2026-07-02` and `03/07/2026`,
- nothing stops two people from "borrowing" the same physical copy.

The goal of this project is to move that spreadsheet into a normalized schema
and let the database enforce the lending rules, instead of trusting whoever is
behind the counter to remember them.

## Status

Work in progress.
