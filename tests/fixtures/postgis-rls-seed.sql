-- Disposable synthetic fixture for the pinned PostGIS cookbook RLS pattern.
-- Run only in the isolated CI database; all coordinates and names are invented.
CREATE EXTENSION IF NOT EXISTS postgis;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'patterns') THEN
        RAISE EXCEPTION 'patterns role already exists; refusing to reuse it';
    END IF;
END
$$;

CREATE ROLE patterns LOGIN CREATEROLE PASSWORD 'patterns';
CREATE SCHEMA demo;
CREATE TABLE demo.service_areas (
    name text PRIMARY KEY,
    geom geometry(Polygon, 4326) NOT NULL
);
CREATE TABLE demo.service_sites (
    site_id integer PRIMARY KEY,
    name text NOT NULL,
    category text NOT NULL,
    geom geometry(Point, 4326) NOT NULL
);
CREATE TABLE demo.parcels (
    parcel_id integer PRIMARY KEY,
    geom geometry(Polygon, 4326) NOT NULL
);

INSERT INTO demo.service_areas (name, geom) VALUES
    ('North service area', ST_MakeEnvelope(-5, -5, 5, 5, 4326)),
    ('Coastal service area', ST_MakeEnvelope(5, 5, 15, 15, 4326));

INSERT INTO demo.service_sites (site_id, name, category, geom) VALUES
    (1, 'North fixture 1', 'synthetic', ST_SetSRID(ST_MakePoint(-2, 0), 4326)),
    (2, 'North fixture 2', 'synthetic', ST_SetSRID(ST_MakePoint(0, 0), 4326)),
    (3, 'North fixture 3', 'synthetic', ST_SetSRID(ST_MakePoint(2, 0), 4326)),
    (4, 'Coastal fixture 1', 'synthetic', ST_SetSRID(ST_MakePoint(7, 7), 4326)),
    (5, 'Coastal fixture 2', 'synthetic', ST_SetSRID(ST_MakePoint(8, 8), 4326)),
    (6, 'Coastal fixture 3', 'synthetic', ST_SetSRID(ST_MakePoint(9, 9), 4326)),
    (7, 'Coastal fixture 4', 'synthetic', ST_SetSRID(ST_MakePoint(10, 10), 4326)),
    (8, 'Outside fixture 1', 'synthetic', ST_SetSRID(ST_MakePoint(20, 20), 4326)),
    (9, 'Outside fixture 2', 'synthetic', ST_SetSRID(ST_MakePoint(30, 30), 4326));

INSERT INTO demo.parcels (parcel_id, geom)
SELECT i,
    CASE
        WHEN i <= 8 THEN ST_Translate(
            ST_MakeEnvelope(-4, -4, -3.5, -3.5, 4326),
            ((i - 1) % 4)::double precision,
            ((i - 1) / 4)::double precision
        )
        WHEN i <= 16 THEN ST_Translate(
            ST_MakeEnvelope(6, 6, 6.5, 6.5, 4326),
            ((i - 9) % 4)::double precision,
            ((i - 9) / 4)::double precision
        )
        ELSE ST_Translate(
            ST_MakeEnvelope(20, 20, 20.5, 20.5, 4326),
            ((i - 17) % 4)::double precision,
            ((i - 17) / 4)::double precision
        )
    END
FROM generate_series(1, 24) AS i;

-- The pattern runner owns the demo objects, but is not a superuser.
ALTER SCHEMA demo OWNER TO patterns;
ALTER TABLE demo.service_areas OWNER TO patterns;
ALTER TABLE demo.service_sites OWNER TO patterns;
ALTER TABLE demo.parcels OWNER TO patterns;
