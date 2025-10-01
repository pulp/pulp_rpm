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

CREATE OR REPLACE FUNCTION pulp_evr_trigger() RETURNS trigger AS $$
  BEGIN
    NEW.evr = (select ROW(coalesce(NEW.epoch::numeric,0),
                          pulp_rpmver_array(coalesce(NEW.version,''))::pulp_evr_array_item[],
                          pulp_rpmver_array(coalesce(NEW.release,''))::pulp_evr_array_item[])::pulp_evr_t);
    RETURN NEW;
  END;
$$ language 'plpgsql';

create or replace FUNCTION pulp_rpmver_array (string1 IN VARCHAR)
  RETURNS pulp_evr_array_item[] as $$
  declare
    input_bytes BYTEA := convert_to(string1, 'ASCII');
    one BYTEA := input_bytes;
    ver_array pulp_evr_array_item[] := ARRAY[]::pulp_evr_array_item[];
    m1_head BYTEA;
    segm1 TEXT;
    segm1_n NUMERIC := 0;
    isnum BOOLEAN;
    pos INTEGER;
  BEGIN
    if string1 is NULL then
      RAISE EXCEPTION 'VALUE_ERROR.';
    end if;

    -- Convert to bytes for proper ASCII handling like Python
    while length(one) > 0 loop
      -- Skip non-alphanumeric characters except ~ and ^
      pos := 1;
      while pos <= length(one) and
            not (get_byte(one, pos-1) between 48 and 57 or    -- 0-9
                 get_byte(one, pos-1) between 65 and 90 or    -- A-Z
                 get_byte(one, pos-1) between 97 and 122 or   -- a-z
                 get_byte(one, pos-1) = 126 or                -- ~
                 get_byte(one, pos-1) = 94)                   -- ^
      loop
        pos := pos + 1;
      end loop;

      if pos > 1 then
        one := substring(one from pos);
      end if;

      if length(one) = 0 then
        exit;
      end if;

      -- Handle tilde - it sorts before everything else
      if get_byte(one, 0) = 126 then -- ~
        ver_array := array_append(ver_array, (NULL, '~')::pulp_evr_array_item);
        one := substring(one from 2);
        continue;
      end if;

      -- Handle caret - it sorts after everything else
      if get_byte(one, 0) = 94 then -- ^
        ver_array := array_append(ver_array, (NULL, '^')::pulp_evr_array_item);
        one := substring(one from 2);
        continue;
      end if;

      -- Extract numeric or alphabetic segment
      if get_byte(one, 0) between 48 and 57 then -- digit
        pos := 1;
        while pos < length(one) and get_byte(one, pos) between 48 and 57 loop
          pos := pos + 1;
        end loop;
        m1_head := substring(one from 1 for pos);
        isnum := true;
      else -- alphabetic
        pos := 1;
        while pos < length(one) and
              (get_byte(one, pos) between 65 and 90 or get_byte(one, pos) between 97 and 122) loop
          pos := pos + 1;
        end loop;
        m1_head := substring(one from 1 for pos);
        isnum := false;
      end if;

      segm1 := convert_from(m1_head, 'ASCII');

      if isnum then
        -- Remove leading zeros for numeric comparison
        segm1 := ltrim(segm1, '0');
        if segm1 = '' then
          segm1_n := 0;
        else
          segm1_n := segm1::numeric;
        end if;
        ver_array := array_append(ver_array, (segm1_n, NULL)::pulp_evr_array_item);
      else
        ver_array := array_append(ver_array, (NULL, segm1)::pulp_evr_array_item);
      end if;

      one := substring(one from pos + 1);
    end loop;

    return ver_array;
  END ;
$$ language 'plpgsql';

-- Version comparison function that matches Python Vercmp.compare logic
CREATE OR REPLACE FUNCTION pulp_vercmp(first_array pulp_evr_array_item[], second_array pulp_evr_array_item[])
  RETURNS INTEGER AS $$
  declare
    i INTEGER := 1;
    max_len INTEGER := greatest(array_length(first_array, 1), array_length(second_array, 1));
    first_item pulp_evr_array_item;
    second_item pulp_evr_array_item;
  BEGIN
    if first_array = second_array then
      return 0;
    end if;

    while i <= coalesce(max_len, 0) loop
      -- Get current segments or null if we've run out
      if i <= array_length(first_array, 1) then
        first_item := first_array[i];
      else
        first_item := (NULL, NULL)::pulp_evr_array_item;
      end if;

      if i <= array_length(second_array, 1) then
        second_item := second_array[i];
      else
        second_item := (NULL, NULL)::pulp_evr_array_item;
      end if;

      -- Handle tilde: ~ sorts before everything else
      if first_item.s = '~' and (second_item.s != '~' OR second_item.s IS NULL) then
        return -1;
      elsif (first_item.s != '~' OR first_item.s IS NULL) and second_item.s = '~' then
        return 1;
      elsif first_item.s = '~' and second_item.s = '~' then
        i := i + 1;
        continue;
      end if;

      -- Handle caret: ^ sorts after regular content, but context matters
      if first_item.s = '^' and second_item.s = '^' then
        -- both have caret, continue comparing
        i := i + 1;
        continue;
      elsif first_item.s = '^' and second_item.s != '^' then
        -- first has caret, second doesn't
        if second_item.s is null and second_item.n is null then
          -- second has ended, first with caret wins
          return 1;
        else
          -- second continues with regular content, caret loses
          return -1;
        end if;
      elsif first_item.s != '^' and second_item.s = '^' then
        -- second has caret, first doesn't
        if first_item.s is null and first_item.n is null then
          -- first has ended, second with caret loses
          return -1;
        else
          -- first continues with regular content, caret loses
          return 1;
        end if;
      end if;

      -- Both items are null (end of both arrays)
      if (first_item.s is null and first_item.n is null) and
         (second_item.s is null and second_item.n is null) then
        return 0;
      end if;

      -- One array ended but the other continues
      if (first_item.s is null and first_item.n is null) then
        return -1;
      elsif (second_item.s is null and second_item.n is null) then
        return 1;
      end if;

      -- Compare numeric vs alphabetic (numeric wins)
      if first_item.n is not null and second_item.s is not null then
        return 1;
      elsif first_item.s is not null and second_item.n is not null then
        return -1;
      end if;

      -- Both numeric
      if first_item.n is not null and second_item.n is not null then
        if first_item.n < second_item.n then
          return -1;
        elsif first_item.n > second_item.n then
          return 1;
        end if;
      -- Both alphabetic
      elsif first_item.s is not null and second_item.s is not null then
        if first_item.s < second_item.s then
          return -1;
        elsif first_item.s > second_item.s then
          return 1;
        end if;
      end if;

      i := i + 1;
    end loop;

    return 0;
  END;
$$ LANGUAGE 'plpgsql';

-- Add comparison operators for pulp_evr_t type
CREATE OR REPLACE FUNCTION pulp_evr_cmp(first_evr pulp_evr_t, second_evr pulp_evr_t)
  RETURNS INTEGER AS $$
  declare
    epoch_cmp INTEGER;
    version_cmp INTEGER;
  BEGIN
    -- Compare epochs first
    epoch_cmp := first_evr.epoch - second_evr.epoch;
    if epoch_cmp != 0 then
      return epoch_cmp;
    end if;

    -- Compare versions
    version_cmp := pulp_vercmp(first_evr.version, second_evr.version);
    if version_cmp != 0 then
      return version_cmp;
    end if;

    -- Compare releases
    return pulp_vercmp(first_evr.release, second_evr.release);
  END;
$$ LANGUAGE 'plpgsql';

-- Create comparison operators
CREATE OR REPLACE FUNCTION pulp_evr_lt(first_evr pulp_evr_t, second_evr pulp_evr_t)
  RETURNS BOOLEAN AS $$
  BEGIN
    return pulp_evr_cmp(first_evr, second_evr) < 0;
  END;
$$ LANGUAGE 'plpgsql';

CREATE OR REPLACE FUNCTION pulp_evr_le(first_evr pulp_evr_t, second_evr pulp_evr_t)
  RETURNS BOOLEAN AS $$
  BEGIN
    return pulp_evr_cmp(first_evr, second_evr) <= 0;
  END;
$$ LANGUAGE 'plpgsql';

CREATE OR REPLACE FUNCTION pulp_evr_eq(first_evr pulp_evr_t, second_evr pulp_evr_t)
  RETURNS BOOLEAN AS $$
  BEGIN
    return pulp_evr_cmp(first_evr, second_evr) = 0;
  END;
$$ LANGUAGE 'plpgsql';

CREATE OR REPLACE FUNCTION pulp_evr_ge(first_evr pulp_evr_t, second_evr pulp_evr_t)
  RETURNS BOOLEAN AS $$
  BEGIN
    return pulp_evr_cmp(first_evr, second_evr) >= 0;
  END;
$$ LANGUAGE 'plpgsql';

CREATE OR REPLACE FUNCTION pulp_evr_gt(first_evr pulp_evr_t, second_evr pulp_evr_t)
  RETURNS BOOLEAN AS $$
  BEGIN
    return pulp_evr_cmp(first_evr, second_evr) > 0;
  END;
$$ LANGUAGE 'plpgsql';

CREATE OR REPLACE FUNCTION pulp_evr_ne(first_evr pulp_evr_t, second_evr pulp_evr_t)
  RETURNS BOOLEAN AS $$
  BEGIN
    return pulp_evr_cmp(first_evr, second_evr) != 0;
  END;
$$ LANGUAGE 'plpgsql';

-- Drop existing operators if they exist
DROP OPERATOR IF EXISTS < (pulp_evr_t, pulp_evr_t);
DROP OPERATOR IF EXISTS <= (pulp_evr_t, pulp_evr_t);
DROP OPERATOR IF EXISTS = (pulp_evr_t, pulp_evr_t);
DROP OPERATOR IF EXISTS <> (pulp_evr_t, pulp_evr_t);
DROP OPERATOR IF EXISTS != (pulp_evr_t, pulp_evr_t);
DROP OPERATOR IF EXISTS >= (pulp_evr_t, pulp_evr_t);
DROP OPERATOR IF EXISTS > (pulp_evr_t, pulp_evr_t);

-- Create operators with proper syntax
CREATE OPERATOR < (
  LEFTARG = pulp_evr_t,
  RIGHTARG = pulp_evr_t,
  FUNCTION = pulp_evr_lt,
  COMMUTATOR = >,
  NEGATOR = >=,
  RESTRICT = scalarltsel,
  JOIN = scalarltjoinsel
);

CREATE OPERATOR <= (
  LEFTARG = pulp_evr_t,
  RIGHTARG = pulp_evr_t,
  FUNCTION = pulp_evr_le,
  COMMUTATOR = >=,
  NEGATOR = >,
  RESTRICT = scalarltsel,
  JOIN = scalarltjoinsel
);

CREATE OPERATOR = (
  LEFTARG = pulp_evr_t,
  RIGHTARG = pulp_evr_t,
  FUNCTION = pulp_evr_eq,
  COMMUTATOR = =,
  NEGATOR = <>,
  RESTRICT = eqsel,
  JOIN = eqjoinsel
);

CREATE OPERATOR <> (
  LEFTARG = pulp_evr_t,
  RIGHTARG = pulp_evr_t,
  FUNCTION = pulp_evr_ne,
  COMMUTATOR = <>,
  NEGATOR = =,
  RESTRICT = neqsel,
  JOIN = neqjoinsel
);

CREATE OPERATOR >= (
  LEFTARG = pulp_evr_t,
  RIGHTARG = pulp_evr_t,
  FUNCTION = pulp_evr_ge,
  COMMUTATOR = <=,
  NEGATOR = <,
  RESTRICT = scalargtsel,
  JOIN = scalargtjoinsel
);

CREATE OPERATOR > (
  LEFTARG = pulp_evr_t,
  RIGHTARG = pulp_evr_t,
  FUNCTION = pulp_evr_gt,
  COMMUTATOR = <,
  NEGATOR = <=,
  RESTRICT = scalargtsel,
  JOIN = scalargtjoinsel
);

-- Create operator class for ordering
DROP OPERATOR CLASS IF EXISTS pulp_evr_ops USING btree;
CREATE OPERATOR CLASS pulp_evr_ops
  DEFAULT FOR TYPE pulp_evr_t USING btree AS
  OPERATOR 1 <,
  OPERATOR 2 <=,
  OPERATOR 3 =,
  OPERATOR 4 >=,
  OPERATOR 5 >,
  FUNCTION 1 pulp_evr_cmp(pulp_evr_t, pulp_evr_t);
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
