# From spreadsheet to 3NF

This is how I got from the café's loan spreadsheet to the tables in
`sql/01_schema.sql`. I wrote it down because the order of the steps matters:
each normal form fixed a problem I could point at in the actual file.

## 0. The starting point (unnormalized)

One row per visit to the counter:

| Date Out | Member Name | Member Email | Member Phone | Membership | Max Games | Games Taken | Publisher | Copy | Shelf | Due Back | Returned |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-08-01 | Hannah Weber | hannah.weber@example.com | +49 151 0000 103 | Plus | 4 | Pandemic; Dixit; Splendor | Z-Man Games; Libellud; Space Cowboys | 1; 1; 1 | C2; B1; A3 | 2026-08-15 | 2026-08-14 |

Problems I found just by reading the file:

- Repeating groups: `Games Taken`, `Publisher`, `Copy` and `Shelf` hold
  lists, and the lists only line up by position. Nothing guarantees the third
  publisher belongs to the third game.
- Update anomalies: Tomás's phone is `+351 912 000 102` in most rows and
  `912000102` in one. Priya is "Basic" everywhere, but one row says her limit
  is 3 games instead of 2. Which row is right? The sheet can't tell you.
- Insertion anomaly: a game the café just bought can't be recorded until
  somebody borrows it, because every row is a loan.
- Deletion anomaly: if the staff clear out old rows (for privacy, say), a
  game nobody borrowed recently disappears from the sheet completely.
- Messy values: `Catan` / `catan`, `Azul ` with a trailing space, two date
  formats, and `Returned` is sometimes a date and sometimes just `yes`.

## 1. First normal form: one value per cell

I split every multi-game row into one row per game copy. The Hannah row above
becomes three rows that share the date, member and due date.

After this, a loan row is identified by
`(Date Out, Member Email, Game, Copy)`.

## 2. Functional dependencies

Before going further I wrote down what determines what. I tried to take these
from the café's rules, not only from the sample data: in the sheet every copy
of Catan sits on shelf B3, so technically `Game → Shelf` holds, but the shelf
is where a physical box lives. If the café buys a third Catan and puts it on
another shelf, a design built on `Game → Shelf` would break.

```
Member Email          → Member Name, Member Phone, Membership
Membership            → Max Games, loan length (7 or 14 days)
Game                  → Publisher
(Game, Copy)          → Shelf
(Date Out, Member Email, Game, Copy) → Due Back, Returned
```

(The loan length isn't a column. I derived it from `Due Back - Date Out`:
it is always 7 days for Basic and 14 for Plus.)

## 3. Second normal form: no partial dependencies

With the composite key from step 1, most columns depend on only *part* of it:

- member columns depend only on `Member Email`,
- `Publisher` depends only on `Game`,
- `Shelf` depends only on `(Game, Copy)`.

So they move into their own tables: `members`, `games` and `copies`.
What stays in `loans` is only what depends on the whole key:
`Due Back` and `Returned`.

## 4. Third normal form: no transitive dependencies

One chain was left inside members:

```
Member Email → Membership → Max Games
```

`Max Games` is a fact about the membership tier, not about the person.
Storing it per member is exactly what produced Priya's "3 games" row.
It moves to `membership_tiers`, together with the loan length.
Publishers get their own table too, so a typo in a publisher name is fixed in
one place.

## 5. Keys

- Surrogate keys (`member_id`, `game_id`, `copy_id`, `loan_id`) for things
  whose natural identifier can change. People change email addresses, and two
  editions of a game can share a title. The natural value still gets a
  `UNIQUE` constraint so duplicates are impossible.
- A natural key for `membership_tiers.tier_code` (`BASIC`, `PLUS`): short,
  stable, and it makes queries readable without a join.

## Result

```
membership_tiers (tier_code PK, loan_limit, loan_days)
members          (member_id PK, full_name, email UNIQUE, phone, tier_code FK)
publishers       (publisher_id PK, name UNIQUE)
games            (game_id PK, title UNIQUE, publisher_id FK)
copies           (copy_id PK, game_id FK, copy_no, shelf, UNIQUE (game_id, copy_no))
loans            (loan_id PK, copy_id FK, member_id FK, lent_on, due_on, returned_on)
```
