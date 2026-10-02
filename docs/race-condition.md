# The "two tills" race condition

Reproduced in `tests/test_concurrency.py`. PostgreSQL's default isolation
level is READ COMMITTED: a statement only sees rows that were committed
before it started. That is exactly what broke the first version of the
"one open loan per copy" rule, which was a trigger doing an `EXISTS` check.

```mermaid
sequenceDiagram
    participant A as Till A
    participant DB as PostgreSQL
    participant B as Till B

    rect rgb(255, 235, 235)
    Note over A,B: Before: BEFORE INSERT trigger with an EXISTS check
    A->>DB: BEGIN, INSERT loan (Catan copy 1)
    DB-->>A: trigger finds no open loan, row inserted
    B->>DB: BEGIN, INSERT loan (Catan copy 1)
    DB-->>B: trigger finds no open loan (A's row is not committed yet)
    A->>DB: COMMIT
    B->>DB: COMMIT
    Note over DB: Catan copy 1 is now lent out twice
    end

    rect rgb(230, 245, 233)
    Note over A,B: After: partial unique index on loans(copy_id) WHERE returned_on IS NULL
    A->>DB: BEGIN, INSERT loan (Catan copy 1)
    DB-->>A: row inserted, index entry for copy 1 taken
    B->>DB: BEGIN, INSERT loan (Catan copy 1)
    Note over DB,B: B waits: A's uncommitted index entry for copy 1 might still commit
    A->>DB: COMMIT
    DB-->>B: ERROR: duplicate key value violates unique constraint
    end
```

## Why not just lock the row?

`SELECT ... FROM copies WHERE copy_id = $1 FOR UPDATE` before inserting
would also serialize the two tills, but only for code that remembers to
take the lock. The unique index protects every insert, including one typed
by hand in psql.
