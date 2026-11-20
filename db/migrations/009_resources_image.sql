-- Imaginea fiecarei resurse (cardurile din catalog si pagina resursei).
-- Fisierele stau in rrm-frontend/public/images, ex. /images/sala-c204.jpg

ALTER TABLE resources
    ADD COLUMN IF NOT EXISTS image_url VARCHAR(255);

-- pentru resursele existente: numele resursei, cu liniute, + .jpg
UPDATE resources
SET image_url = '/images/'
    || lower(trim(both '-' FROM regexp_replace(name, '[^A-Za-z0-9]+', '-', 'g')))
    || '.jpg'
WHERE image_url IS NULL;
