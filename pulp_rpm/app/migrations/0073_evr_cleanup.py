
# This Migration was _not_ automatically generated.
# When regenerating the migrations ever, this one _must_ be preserved.
#
# Phase 2 of EVR sort key migration (cleanup).
#
# Drops the old 'evr' column, old types (pulp_evr_t, pulp_evr_array_item),
# and old helper functions. Updates the trigger to only maintain evr_v2.
#
# This migration should only be applied AFTER deploying code that reads
# from evr_v2 (via db_column='evr_v2' on the model field).

from django.db import migrations

cleanup_sql = """
-- Drop old triggers (will be recreated below)
DROP TRIGGER IF EXISTS pulp_evr_insert_trigger ON rpm_package;
DROP TRIGGER IF EXISTS pulp_evr_update_trigger ON rpm_package;

-- Drop old evr column and its type infrastructure
ALTER TABLE rpm_package DROP COLUMN evr;

DROP FUNCTION IF EXISTS pulp_rpmver_array(VARCHAR);
DROP FUNCTION IF EXISTS pulp_isdigit(CHAR);
DROP FUNCTION IF EXISTS pulp_isalphanum(CHAR);
DROP FUNCTION IF EXISTS pulp_isempty(TEXT);

DROP TYPE IF EXISTS pulp_evr_t;
DROP TYPE IF EXISTS pulp_evr_array_item;

-- Replace trigger function to only maintain evr_v2
CREATE OR REPLACE FUNCTION pulp_evr_trigger() RETURNS trigger AS $$
BEGIN
    NEW.evr_v2 = pulp_rpm_evr_sortkey(NEW.epoch, NEW.version, NEW.release);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Recreate triggers
CREATE TRIGGER pulp_evr_insert_trigger
    BEFORE INSERT
    ON rpm_package
    FOR EACH ROW
    EXECUTE PROCEDURE pulp_evr_trigger();

CREATE TRIGGER pulp_evr_update_trigger
    BEFORE UPDATE OF epoch, version, release
    ON rpm_package
    FOR EACH ROW
    WHEN (
        OLD.epoch IS DISTINCT FROM NEW.epoch OR
        OLD.version IS DISTINCT FROM NEW.version OR
        OLD.release IS DISTINCT FROM NEW.release
    )
    EXECUTE PROCEDURE pulp_evr_trigger();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0072_fix_evr_version_sorting'),
    ]

    operations = [
        migrations.RunSQL(cleanup_sql),
    ]
