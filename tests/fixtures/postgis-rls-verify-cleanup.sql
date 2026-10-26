-- Assertions after the pinned PostGIS cookbook pattern runs.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname IN (
            'postgis_cb_north_ops',
            'postgis_cb_coastal_ops',
            'postgis_cb_read_all_geo'
        )
    ) THEN
        RAISE EXCEPTION 'cookbook pattern leaked one or more temporary roles';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'demo'
          AND policyname LIKE 'postgis_cb_%'
    ) THEN
        RAISE EXCEPTION 'cookbook pattern leaked one or more temporary policies';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'demo'
          AND c.relname IN ('service_sites', 'parcels')
          AND (c.relrowsecurity OR c.relforcerowsecurity)
    ) THEN
        RAISE EXCEPTION 'cookbook pattern did not restore original RLS flags';
    END IF;

    IF (SELECT count(*) FROM demo.service_sites) <> 9 THEN
        RAISE EXCEPTION 'fixture site count changed';
    END IF;

    IF (SELECT count(*) FROM demo.parcels) <> 24 THEN
        RAISE EXCEPTION 'fixture parcel count changed';
    END IF;
END
$$;

SELECT
    (SELECT count(*) FROM demo.service_sites) AS synthetic_site_count,
    (SELECT count(*) FROM demo.parcels) AS synthetic_parcel_count,
    'temporary roles/policies cleaned up; fixture counts restored' AS result;
