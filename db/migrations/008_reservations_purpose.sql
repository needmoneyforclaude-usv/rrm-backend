-- NEED-27: scopul rezervarii (campul "Scop" din dialogul de rezervare).

ALTER TABLE reservations
    ADD COLUMN IF NOT EXISTS purpose VARCHAR(255);
