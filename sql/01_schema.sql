-- Core tables. docs/normalization.md explains how they were derived
-- from the original spreadsheet.

CREATE TABLE membership_tiers (
    tier_code   text     PRIMARY KEY,
    loan_limit  smallint NOT NULL CHECK (loan_limit > 0),
    loan_days   smallint NOT NULL CHECK (loan_days > 0)
);

CREATE TABLE members (
    member_id  integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name  text NOT NULL,
    -- Stored lowercase so "Maya@x.com" and "maya@x.com" can't both exist.
    email      text NOT NULL UNIQUE CHECK (email = lower(email)),
    phone      text,
    tier_code  text NOT NULL REFERENCES membership_tiers (tier_code)
);

CREATE TABLE publishers (
    publisher_id  integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          text NOT NULL UNIQUE
);

CREATE TABLE games (
    game_id       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title         text    NOT NULL UNIQUE,
    publisher_id  integer NOT NULL REFERENCES publishers (publisher_id)
);

-- A copy is one physical box. The shelf lives here, not on games,
-- because two copies of the same game can sit on different shelves.
CREATE TABLE copies (
    copy_id  integer  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    game_id  integer  NOT NULL REFERENCES games (game_id),
    copy_no  smallint NOT NULL CHECK (copy_no > 0),
    shelf    text     NOT NULL,
    UNIQUE (game_id, copy_no)
);

CREATE TABLE loans (
    loan_id      integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    copy_id      integer NOT NULL REFERENCES copies (copy_id),
    member_id    integer NOT NULL REFERENCES members (member_id),
    lent_on      date    NOT NULL DEFAULT current_date,
    due_on       date    NOT NULL,
    returned_on  date,   -- NULL means the game is still out
    CHECK (due_on > lent_on),
    CHECK (returned_on IS NULL OR returned_on >= lent_on)
);

INSERT INTO membership_tiers (tier_code, loan_limit, loan_days) VALUES
    ('BASIC', 2, 7),
    ('PLUS',  4, 14);
