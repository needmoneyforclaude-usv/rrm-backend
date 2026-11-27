ALTER TABLE reservations
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW();

ALTER TABLE reservations
    DROP CONSTRAINT IF EXISTS reservations_status_check;
ALTER TABLE reservations
    ADD CONSTRAINT reservations_status_check
    CHECK (status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'EXPIRED',
                      'COMPLETED'));
