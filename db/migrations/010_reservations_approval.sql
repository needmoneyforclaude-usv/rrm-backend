UPDATE reservations SET status = 'EXPIRED'
WHERE status = 'PENDING' AND start_time <= NOW();

ALTER TABLE reservations
    DROP CONSTRAINT IF EXISTS reservations_status_check;
ALTER TABLE reservations
    ADD CONSTRAINT reservations_status_check
    CHECK (status IN ('PENDING', 'CONFIRMED', 'REJECTED', 'CANCELLED',
                      'EXPIRED', 'COMPLETED'));

ALTER TABLE reservations
    DROP CONSTRAINT IF EXISTS reservations_no_overlap;
ALTER TABLE reservations
    ADD CONSTRAINT reservations_no_overlap
    EXCLUDE USING gist (
        resource_id WITH =,
        tsrange(start_time, end_time) WITH &&
    ) WHERE (status = 'CONFIRMED');
