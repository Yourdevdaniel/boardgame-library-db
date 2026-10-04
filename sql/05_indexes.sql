-- PostgreSQL creates indexes for PRIMARY KEY and UNIQUE automatically,
-- but NOT for foreign keys. With 500k loans (seed_bulk.py) the two
-- screens below were doing a full scan of the loans table every time.
-- Before/after plans are in docs/query-tuning.md.

-- "Show this member's loans" (and the loan-limit count in lend_copy).
CREATE INDEX loans_member_id_idx ON loans (member_id);

-- "Show this copy's history" (is this box lent out constantly?).
CREATE INDEX loans_copy_id_idx ON loans (copy_id);

-- Not indexed on purpose: copies.game_id, games.publisher_id and
-- members.tier_code. Those tables have a few thousand rows at most, and a
-- sequential scan of them was already faster than 1 ms.
