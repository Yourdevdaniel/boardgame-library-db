# Query tuning with 500,000 loans

`python db.py && python seed_bulk.py` builds a database with 20,000 members,
2,750 copies and 500,139 loans (three years of made-up history, about 140
games out right now). The numbers below come from `EXPLAIN (ANALYZE)` on my
laptop with a warm cache. They are single runs, so read them as orders of
magnitude, not benchmarks.

## What I measured

| Query | Before `05_indexes.sql` | After |
|---|---|---|
| A member's loan history (25 rows, joined to copies and games) | Parallel Seq Scan on loans, 100.6 ms | Bitmap Index Scan on `loans_member_id_idx`, 2.6 ms |
| `SELECT * FROM loans WHERE member_id = 4242` | Parallel Seq Scan, 119.3 ms | Bitmap Index Scan, 0.14 ms |
| A copy's loan history (199 rows) | Parallel Seq Scan on loans, 83.4 ms | Bitmap Index Scan on `loans_copy_id_idx`, 1.6 ms |
| The open-loan count inside `lend_copy` | Bitmap Index Scan on `one_open_loan_per_copy`, 0.12 ms | same plan, 0.16 ms |
| `SELECT * FROM overdue_loans` (78 rows) | Bitmap Index Scan on `one_open_loan_per_copy`, 2.3 ms | 12 to 27 ms, see below |

## What surprised me

Foreign keys are not indexed automatically. PostgreSQL creates an index
for every PRIMARY KEY and UNIQUE constraint, so I assumed `loans.member_id`
had one too. It didn't: every "show me this member's loans" read all 500k
rows (`Rows Removed by Filter: 166705`, per worker, times three workers).

The index I added for correctness also made two queries fast. The
partial unique index from the race-condition fix
(`loans(copy_id) WHERE returned_on IS NULL`) only holds the ~140 open
loans. Any query that filters on `returned_on IS NULL` can use it, so the
overdue report and the loan-limit count in `lend_copy` were already fast
before I touched them.

The overdue report got slower after I re-ran ANALYZE, not because of the
new indexes. ANALYZE samples rows, and the second sample estimated 200
open loans instead of 139. With that estimate the planner switched from
nested loops to hash joins, which read all 20,000 members. I checked by
dropping the two new indexes inside a transaction: the plan stayed the
same. At 12 to 27 ms for a report the staff open a few times a day, I left
it alone rather than tune statistics.

## What I decided not to index

- A composite `(member_id, lent_on)` index to avoid sorting the member
  history. A member has ~25 loans; the sort step added about 0.1 ms.
- `copies.game_id` and `games.publisher_id`: those tables have a few
  thousand rows, and scanning them is already under a millisecond.
- `members.tier_code`: it only has two distinct values, so an index on
  it would almost never be selective enough for the planner to use.

## Cost

Every index is extra work on INSERT. Seeding the 500k loans took 26.8 s
without the two indexes and 27.7 to 31.9 s with them, which is within the
noise of running it twice.

## Reproducing

```sql
BEGIN;
DROP INDEX loans_member_id_idx;  -- as if it had never been created
EXPLAIN (ANALYZE, COSTS OFF) SELECT * FROM loans WHERE member_id = 4242;
ROLLBACK;                         -- the index is back
EXPLAIN (ANALYZE, COSTS OFF) SELECT * FROM loans WHERE member_id = 4242;
```

`DROP INDEX` is transactional in PostgreSQL, so this compares both plans
without actually losing the index. (It does lock the table until the
ROLLBACK, so not something to run on a busy production database.)
