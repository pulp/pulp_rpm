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

-- Version comparison function that matches C rpmvercmp logic exactly
CREATE OR REPLACE FUNCTION pulp_vercmp(first_array pulp_evr_array_item[], second_array pulp_evr_array_item[])
  RETURNS INTEGER AS $$
  declare
    first_str TEXT := '';
    second_str TEXT := '';
    i INTEGER;
  BEGIN
    -- Convert arrays back to strings for C-style processing
    -- This is necessary because the C algorithm works on strings, not pre-parsed arrays

    -- Reconstruct first string
    for i in 1..coalesce(array_length(first_array, 1), 0) loop
      if first_array[i].n IS NOT NULL then
        first_str := first_str || first_array[i].n::text;
      elsif first_array[i].s IS NOT NULL then
        first_str := first_str || first_array[i].s;
      end if;
    end loop;

    -- Reconstruct second string
    for i in 1..coalesce(array_length(second_array, 1), 0) loop
      if second_array[i].n IS NOT NULL then
        second_str := second_str || second_array[i].n::text;
      elsif second_array[i].s IS NOT NULL then
        second_str := second_str || second_array[i].s;
      end if;
    end loop;

    -- Now call the C-style comparison
    return pulp_vercmp_string(first_str, second_str);
  END;
$$ LANGUAGE 'plpgsql';

-- Direct port of C rpmvercmp logic
CREATE OR REPLACE FUNCTION pulp_vercmp_string(str1 TEXT, str2 TEXT)
  RETURNS INTEGER AS $$
  declare
    one_pos INTEGER := 1;
    two_pos INTEGER := 1;
    str1_len INTEGER := length(str1);
    str2_len INTEGER := length(str2);
    one_char TEXT;
    two_char TEXT;
    seg1_start INTEGER;
    seg2_start INTEGER;
    seg1_end INTEGER;
    seg2_end INTEGER;
    seg1 TEXT;
    seg2 TEXT;
    isnum BOOLEAN;
    one_len INTEGER;
    two_len INTEGER;
    cmp_result INTEGER;
  BEGIN
    -- Easy comparison to see if versions are identical
    if str1 = str2 then
      return 0;
    end if;

    -- Loop through each version segment and compare them
    while one_pos <= str1_len OR two_pos <= str2_len loop
      -- Skip non-alphanumeric characters except ~ and ^
      while one_pos <= str1_len loop
        one_char := substring(str1, one_pos, 1);
        if (one_char >= 'a' and one_char <= 'z') or
           (one_char >= 'A' and one_char <= 'Z') or
           (one_char >= '0' and one_char <= '9') or
           one_char = '~' or one_char = '^' then
          exit;
        end if;
        one_pos := one_pos + 1;
      end loop;

      while two_pos <= str2_len loop
        two_char := substring(str2, two_pos, 1);
        if (two_char >= 'a' and two_char <= 'z') or
           (two_char >= 'A' and two_char <= 'Z') or
           (two_char >= '0' and two_char <= '9') or
           two_char = '~' or two_char = '^' then
          exit;
        end if;
        two_pos := two_pos + 1;
      end loop;

      -- Get current characters (or empty if past end)
      one_char := case when one_pos <= str1_len then substring(str1, one_pos, 1) else '' end;
      two_char := case when two_pos <= str2_len then substring(str2, two_pos, 1) else '' end;

      -- Handle tilde separator - sorts before everything else
      if one_char = '~' or two_char = '~' then
        if one_char != '~' then return 1; end if;
        if two_char != '~' then return -1; end if;
        one_pos := one_pos + 1;
        two_pos := two_pos + 1;
        continue;
      end if;

      -- Handle caret separator - context dependent like C code
      if one_char = '^' or two_char = '^' then
        if one_pos > str1_len then return -1; end if;  -- !*one
        if two_pos > str2_len then return 1; end if;   -- !*two
        if one_char != '^' then return 1; end if;
        if two_char != '^' then return -1; end if;
        one_pos := one_pos + 1;
        two_pos := two_pos + 1;
        continue;
      end if;

      -- If we ran to the end of either, we are finished with the loop
      if not (one_pos <= str1_len and two_pos <= str2_len) then
        exit;
      end if;

      -- Grab first completely alpha or completely numeric segment
      seg1_start := one_pos;
      seg2_start := two_pos;

      if one_char >= '0' and one_char <= '9' then
        -- Numeric segment
        while one_pos <= str1_len and substring(str1, one_pos, 1) >= '0' and substring(str1, one_pos, 1) <= '9' loop
          one_pos := one_pos + 1;
        end loop;
        while two_pos <= str2_len and substring(str2, two_pos, 1) >= '0' and substring(str2, two_pos, 1) <= '9' loop
          two_pos := two_pos + 1;
        end loop;
        isnum := true;
      else
        -- Alpha segment
        while one_pos <= str1_len loop
          one_char := substring(str1, one_pos, 1);
          if not ((one_char >= 'a' and one_char <= 'z') or (one_char >= 'A' and one_char <= 'Z')) then
            exit;
          end if;
          one_pos := one_pos + 1;
        end loop;
        while two_pos <= str2_len loop
          two_char := substring(str2, two_pos, 1);
          if not ((two_char >= 'a' and two_char <= 'z') or (two_char >= 'A' and two_char <= 'Z')) then
            exit;
          end if;
          two_pos := two_pos + 1;
        end loop;
        isnum := false;
      end if;

      -- Extract the segments
      seg1 := substring(str1, seg1_start, one_pos - seg1_start);
      seg2 := substring(str2, seg2_start, two_pos - seg2_start);

      -- Handle empty segments (matching C logic exactly)
      if seg1_start = one_pos then return -1; end if;  -- arbitrary, matches C

      -- Take care of different types: numeric vs alpha
      if seg2_start = two_pos then
        return case when isnum then 1 else -1 end;
      end if;

      if isnum then
        -- Numeric comparison
        -- Throw away leading zeros
        seg1 := ltrim(seg1, '0');
        seg2 := ltrim(seg2, '0');

        -- Whichever number has more digits wins
        one_len := length(seg1);
        two_len := length(seg2);
        if one_len > two_len then return 1; end if;
        if two_len > one_len then return -1; end if;
      end if;

      -- String comparison (works for both alpha and same-length numeric)
      if seg1 < seg2 then
        return -1;
      elsif seg1 > seg2 then
        return 1;
      end if;
      -- Equal segments, continue to next

    end loop;

    -- Handle end conditions
    if one_pos > str1_len and two_pos > str2_len then
      return 0;  -- both ended
    elsif one_pos > str1_len then
      return -1;  -- first ended, second continues
    else
      return 1;   -- second ended, first continues
    end if;
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
