
# This Migration was _not_ automatically generated.
# When regenerating the migrations ever, this one _must_ be preserved.

from django.db import migrations
from pulp_rpm.app.models.package import RpmVersionField

extension_sql = """
create type pulp_evr_array_item as (
  n       NUMERIC,
  s       TEXT
);

create type pulp_evr_t as (
  epoch INT,
  version pulp_evr_array_item[],
  release pulp_evr_array_item[]
);

CREATE FUNCTION pulp_evr_trigger() RETURNS trigger AS $$
  BEGIN
    NEW.evr = (select ROW(coalesce(NEW.epoch::numeric,0),
                          pulp_rpmver_array(coalesce(NEW.version,'pulp_isempty'))::pulp_evr_array_item[],
                          pulp_rpmver_array(coalesce(NEW.release,'pulp_isempty'))::pulp_evr_array_item[])::pulp_evr_t);
    RETURN NEW;
  END;
$$ language 'plpgsql';

create or replace FUNCTION pulp_isempty(t TEXT)
  RETURNS BOOLEAN as $$
  BEGIN
    return t ~ '^[[:space:]]*$';
  END;
$$ language 'plpgsql';

create or replace FUNCTION pulp_isalphanum(ch CHAR)
  RETURNS BOOLEAN as $$
  BEGIN
    if ascii(ch) between ascii('a') and ascii('z') or
      ascii(ch) between ascii('A') and ascii('Z') or
      ascii(ch) between ascii('0') and ascii('9')
    then
      return TRUE;
    end if;
    return FALSE;
  END;
$$ language 'plpgsql';

create or replace function pulp_isdigit(ch CHAR)
  RETURNS BOOLEAN as $$
  BEGIN
    if ascii(ch) between ascii('0') and ascii('9')
    then
    return TRUE;
    end if;
    return FALSE;
  END ;
$$ language 'plpgsql';

create or replace FUNCTION pulp_rpmver_array (string1 IN VARCHAR)
  RETURNS pulp_evr_array_item[] as $$
  declare
    str1 VARCHAR := string1;
    digits VARCHAR(10) := '0123456789';
    lc_alpha VARCHAR(27) := 'abcdefghijklmnopqrstuvwxyz';
    uc_alpha VARCHAR(27) := 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    alpha VARCHAR(54) := lc_alpha || uc_alpha;
    one VARCHAR;
    isnum BOOLEAN;
    ver_array pulp_evr_array_item[] := ARRAY[]::pulp_evr_array_item[];
  BEGIN
    if str1 is NULL
    then
      RAISE EXCEPTION 'VALUE_ERROR.';
    end if;

    one := str1;
    <<segment_loop>>
    while one <> ''
    loop
      declare
        segm1 VARCHAR;
        segm1_n NUMERIC := 0;
      begin
        -- Throw out all non-alphanum characters
        while one <> '' and not pulp_isalphanum(one)
        loop
          one := substr(one, 2);
        end loop;
        str1 := one;
        if str1 <> '' and pulp_isdigit(str1)
        then
          str1 := ltrim(str1, digits);
          isnum := true;
        else
          str1 := ltrim(str1, alpha);
          isnum := false;
        end if;
        if str1 <> ''
        then segm1 := substr(one, 1, length(one) - length(str1));
        else segm1 := one;
        end if;

        if segm1 = '' then return ver_array; end if; /* arbitrary */
        if isnum
        then
          segm1 := ltrim(segm1, '0');
          if segm1 <> '' then segm1_n := segm1::numeric; end if;
          segm1 := NULL;
        else
        end if;
        ver_array := array_append(ver_array, (segm1_n, segm1)::pulp_evr_array_item);
        one := str1;
      end;
    end loop segment_loop;

    return ver_array;
  END ;
$$ language 'plpgsql';
"""


triggers_sql = """
-- create pulp_evr_t on insert, so it matches the provided E/V/R cols
CREATE TRIGGER pulp_evr_insert_trigger
  BEFORE INSERT
  ON rpm_package
  FOR EACH ROW
  EXECUTE PROCEDURE pulp_evr_trigger();

-- create pulp_evr_t on update, so it continues to match the provided E/V/R cols, but only if Something Changed
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

# update existing Packages to populate their evr field
migration_sql = """
update rpm_package set evr = (
  select ROW(coalesce(epoch::numeric,0),
             pulp_rpmver_array(version)::pulp_evr_array_item[],
             pulp_rpmver_array(release)::pulp_evr_array_item[])::pulp_evr_t
  );
"""


class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0012_remove_pkg_group_env_cat_related_pkgs'),
    ]

    operations = [
        migrations.RunSQL(extension_sql),
        migrations.RunSQL(triggers_sql),
        migrations.AddField(
            model_name='package',
            name='evr',
            field=RpmVersionField(null=True),
            preserve_default=False,
        ),
        migrations.RunSQL(migration_sql),
        migrations.AlterField(
            model_name='package',
            name='evr',
            field=RpmVersionField(null=False),
        )
    ]
