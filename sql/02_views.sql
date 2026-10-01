-- Read-only views for the questions the staff ask every day.

-- "Who do we need to call?"
CREATE VIEW overdue_loans AS
SELECT l.loan_id,
       m.full_name,
       m.email,
       m.phone,
       g.title,
       c.copy_no,
       l.lent_on,
       l.due_on,
       current_date - l.due_on AS days_overdue
FROM loans l
JOIN members m ON m.member_id = l.member_id
JOIN copies  c ON c.copy_id   = l.copy_id
JOIN games   g ON g.game_id   = c.game_id
WHERE l.returned_on IS NULL
  AND l.due_on < current_date;

-- "Which copies are on the shelf right now?"
CREATE VIEW available_copies AS
SELECT c.copy_id, g.title, c.copy_no, c.shelf
FROM copies c
JOIN games g ON g.game_id = c.game_id
WHERE NOT EXISTS (
    SELECT 1 FROM loans l
    WHERE l.copy_id = c.copy_id
      AND l.returned_on IS NULL
);

-- "Should we buy another copy of anything?"
-- LEFT JOIN so games that were never lent still show up with 0.
CREATE VIEW game_popularity AS
SELECT g.title,
       count(DISTINCT c.copy_id)                            AS copies_owned,
       count(l.loan_id)                                     AS times_lent,
       count(l.loan_id) FILTER (WHERE l.returned_on IS NULL) AS out_now
FROM games g
JOIN copies c     ON c.game_id = g.game_id
LEFT JOIN loans l ON l.copy_id = c.copy_id
GROUP BY g.game_id, g.title;
