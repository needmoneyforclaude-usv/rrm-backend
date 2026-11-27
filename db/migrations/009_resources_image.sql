ALTER TABLE resources
    ADD COLUMN IF NOT EXISTS image_url VARCHAR(255);

UPDATE resources
SET image_url = '/images/'
    || lower(trim(both '-' FROM regexp_replace(name, '[^A-Za-z0-9]+', '-', 'g')))
    || '.jpg'
WHERE image_url IS NULL;
