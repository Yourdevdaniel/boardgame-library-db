-- Lending and returning, with every rule checked in one place.
-- Staff tools call these instead of writing to the loans table directly.
--
-- lend_copy is a FUNCTION because the caller needs the new loan_id back
-- (SELECT lend_copy(...)). return_copy has nothing to return, so it is a
-- PROCEDURE (CALL return_copy(...)).

CREATE FUNCTION lend_copy(p_member_id integer, p_copy_id integer)
RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    v_limit    smallint;
    v_open     integer;
    v_loan_id  integer;
BEGIN
    SELECT t.loan_limit
      INTO v_limit
      FROM members m
      JOIN membership_tiers t ON t.tier_code = m.tier_code
     WHERE m.member_id = p_member_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'member % does not exist', p_member_id;
    END IF;

    IF EXISTS (SELECT 1 FROM loans
               WHERE member_id = p_member_id
                 AND returned_on IS NULL
                 AND due_on < current_date) THEN
        RAISE EXCEPTION 'member % has an overdue game and must return it first', p_member_id;
    END IF;

    SELECT count(*)
      INTO v_open
      FROM loans
     WHERE member_id = p_member_id
       AND returned_on IS NULL;
    IF v_open >= v_limit THEN
        RAISE EXCEPTION 'member % already has % of % games', p_member_id, v_open, v_limit;
    END IF;

    -- Only here for a readable message. The real guarantee is the
    -- one_open_loan_per_copy index (see docs/race-condition.md).
    IF EXISTS (SELECT 1 FROM loans WHERE copy_id = p_copy_id AND returned_on IS NULL) THEN
        RAISE EXCEPTION 'copy % is already lent out', p_copy_id;
    END IF;

    INSERT INTO loans (copy_id, member_id)
    VALUES (p_copy_id, p_member_id)
    RETURNING loan_id INTO v_loan_id;

    RETURN v_loan_id;
END;
$$;


CREATE PROCEDURE return_copy(p_loan_id integer)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE loans
       SET returned_on = current_date
     WHERE loan_id = p_loan_id
       AND returned_on IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'loan % does not exist or was already returned', p_loan_id;
    END IF;
END;
$$;
