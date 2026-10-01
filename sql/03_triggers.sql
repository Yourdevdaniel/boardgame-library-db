-- Triggers that keep the loans table honest.

-- 1. If no due date is given, work it out from the member's tier
--    (7 days for BASIC, 14 for PLUS). A BEFORE trigger can still change
--    NEW, and NOT NULL is only checked after it runs.
CREATE FUNCTION set_due_date() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.due_on IS NULL THEN
        SELECT NEW.lent_on + t.loan_days
          INTO NEW.due_on
          FROM members m
          JOIN membership_tiers t ON t.tier_code = m.tier_code
         WHERE m.member_id = NEW.member_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER loans_set_due_date
BEFORE INSERT ON loans
FOR EACH ROW EXECUTE FUNCTION set_due_date();


-- 2. A copy can't be lent while it is still out.
CREATE FUNCTION check_copy_is_available() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM loans
               WHERE copy_id = NEW.copy_id
                 AND returned_on IS NULL) THEN
        RAISE EXCEPTION 'copy % is already lent out', NEW.copy_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER loans_one_open_loan_per_copy
BEFORE INSERT ON loans
FOR EACH ROW EXECUTE FUNCTION check_copy_is_available();

