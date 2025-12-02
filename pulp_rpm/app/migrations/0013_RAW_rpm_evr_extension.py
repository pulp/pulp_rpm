
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
  version TEXT,
  release TEXT
);

CREATE OR REPLACE FUNCTION pulp_evr_trigger() RETURNS trigger AS $$
  BEGIN
    NEW.evr = (select ROW(coalesce(NEW.epoch::numeric,0),
                          coalesce(NEW.version,''),
                          coalesce(NEW.release,''))::pulp_evr_t);
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

-- Compare two version strings according to RPM version comparison rules
create or replace FUNCTION pulp_rpmvercmp(a TEXT, b TEXT)
  RETURNS INT as $$
  declare
    one TEXT;
    two TEXT;
    a_part TEXT;
    b_part TEXT;
    a_segment TEXT;
    b_segment TEXT;
    isnum BOOLEAN;
    result INT;
  BEGIN
    -- Fast path for identical strings
    if a = b then
      return 0;
    end if;

    one := a;
    two := b;

    -- Loop through each version segment
    while length(one) > 0 or length(two) > 0
    loop
      -- Strip leading non-alphanumeric characters (except ~ and ^)
      while length(one) > 0 and not pulp_isalphanum(one) and substr(one, 1, 1) <> '~' and substr(one, 1, 1) <> '^'
      loop
        one := substr(one, 2);
      end loop;

      while length(two) > 0 and not pulp_isalphanum(two) and substr(two, 1, 1) <> '~' and substr(two, 1, 1) <> '^'
      loop
        two := substr(two, 2);
      end loop;

      -- Handle tilde separator - it sorts before everything else
      if (length(one) > 0 and substr(one, 1, 1) = '~') or (length(two) > 0 and substr(two, 1, 1) = '~') then
        if length(one) = 0 or substr(one, 1, 1) <> '~' then
          return 1;  -- one > two (no tilde beats tilde)
        end if;
        if length(two) = 0 or substr(two, 1, 1) <> '~' then
          return -1;  -- one < two (tilde loses to no tilde)
        end if;
        -- Both have tilde, strip and continue
        one := substr(one, 2);
        two := substr(two, 2);
        continue;
      end if;

      -- Handle caret separator - complex logic
      -- Caret vs end-of-string: caret wins (is greater)
      -- Caret vs continuation: continuation wins (is greater)
      if (length(one) > 0 and substr(one, 1, 1) = '^') or (length(two) > 0 and substr(two, 1, 1) = '^') then
        if length(one) = 0 or substr(one, 1, 1) <> '^' then
          -- one continues or ended, two has caret
          if length(one) = 0 then
            return -1;  -- end < caret
          else
            return 1;  -- continuation > caret
          end if;
        end if;
        if length(two) = 0 or substr(two, 1, 1) <> '^' then
          -- one has caret, two continues or ended
          if length(two) = 0 then
            return 1;  -- caret > end
          else
            return -1;  -- caret < continuation
          end if;
        end if;
        -- Both have caret, strip and continue
        one := substr(one, 2);
        two := substr(two, 2);
        continue;
      end if;

      -- If we ran to the end of either, we are finished
      if length(one) = 0 and length(two) = 0 then
        return 0;
      elsif length(one) = 0 then
        return -1;
      elsif length(two) = 0 then
        return 1;
      end if;

      -- Determine if this segment is numeric or alpha
      if pulp_isdigit(substr(one, 1, 1)) then
        isnum := true;
        -- Extract numeric segment from both
        a_segment := '';
        while length(one) > 0 and pulp_isdigit(substr(one, 1, 1))
        loop
          a_segment := a_segment || substr(one, 1, 1);
          one := substr(one, 2);
        end loop;

        b_segment := '';
        while length(two) > 0 and pulp_isdigit(substr(two, 1, 1))
        loop
          b_segment := b_segment || substr(two, 1, 1);
          two := substr(two, 2);
        end loop;

        -- If second segment is not numeric, numeric wins
        if length(b_segment) = 0 then
          return 1;
        end if;

        -- Strip leading zeros
        a_segment := ltrim(a_segment, '0');
        b_segment := ltrim(b_segment, '0');
        if length(a_segment) = 0 then a_segment := '0'; end if;
        if length(b_segment) = 0 then b_segment := '0'; end if;

        -- Compare by length first (longer number = bigger)
        if length(a_segment) < length(b_segment) then
          return -1;
        elsif length(a_segment) > length(b_segment) then
          return 1;
        end if;

        -- Same length, compare as strings
        if a_segment < b_segment then
          return -1;
        elsif a_segment > b_segment then
          return 1;
        end if;
      else
        -- Extract alpha segment from both
        a_segment := '';
        while length(one) > 0 and pulp_isalphanum(one) and not pulp_isdigit(substr(one, 1, 1))
        loop
          a_segment := a_segment || substr(one, 1, 1);
          one := substr(one, 2);
        end loop;

        b_segment := '';
        while length(two) > 0 and pulp_isalphanum(two) and not pulp_isdigit(substr(two, 1, 1))
        loop
          b_segment := b_segment || substr(two, 1, 1);
          two := substr(two, 2);
        end loop;

        -- If first segment is empty, arbitrary
        if length(a_segment) = 0 then
          return -1;
        end if;

        -- If second is numeric and first is alpha, numeric wins
        if length(b_segment) = 0 and length(two) > 0 and pulp_isdigit(substr(two, 1, 1)) then
          return -1;
        end if;

        -- Compare alphabetically
        if a_segment < b_segment then
          return -1;
        elsif a_segment > b_segment then
          return 1;
        end if;
      end if;
    end loop;

    return 0;
  END;
$$ language 'plpgsql' IMMUTABLE;

-- Compare two EVR composite types
create or replace FUNCTION pulp_evr_cmp(a pulp_evr_t, b pulp_evr_t)
  RETURNS INT as $$
  declare
    result INT;
  BEGIN
    -- Compare epoch first
    if a.epoch < b.epoch then
      return -1;
    elsif a.epoch > b.epoch then
      return 1;
    end if;

    -- Compare version
    result := pulp_rpmvercmp(a.version, b.version);
    if result <> 0 then
      return result;
    end if;

    -- Compare release
    return pulp_rpmvercmp(a.release, b.release);
  END;
$$ language 'plpgsql' IMMUTABLE;

-- Define comparison operators for pulp_evr_t
CREATE OR REPLACE FUNCTION pulp_evr_eq(a pulp_evr_t, b pulp_evr_t)
  RETURNS BOOLEAN as $$
  BEGIN
    return pulp_evr_cmp(a, b) = 0;
  END;
$$ language 'plpgsql' IMMUTABLE;

CREATE OR REPLACE FUNCTION pulp_evr_ne(a pulp_evr_t, b pulp_evr_t)
  RETURNS BOOLEAN as $$
  BEGIN
    return pulp_evr_cmp(a, b) <> 0;
  END;
$$ language 'plpgsql' IMMUTABLE;

CREATE OR REPLACE FUNCTION pulp_evr_lt(a pulp_evr_t, b pulp_evr_t)
  RETURNS BOOLEAN as $$
  BEGIN
    return pulp_evr_cmp(a, b) < 0;
  END;
$$ language 'plpgsql' IMMUTABLE;

CREATE OR REPLACE FUNCTION pulp_evr_le(a pulp_evr_t, b pulp_evr_t)
  RETURNS BOOLEAN as $$
  BEGIN
    return pulp_evr_cmp(a, b) <= 0;
  END;
$$ language 'plpgsql' IMMUTABLE;

CREATE OR REPLACE FUNCTION pulp_evr_gt(a pulp_evr_t, b pulp_evr_t)
  RETURNS BOOLEAN as $$
  BEGIN
    return pulp_evr_cmp(a, b) > 0;
  END;
$$ language 'plpgsql' IMMUTABLE;

CREATE OR REPLACE FUNCTION pulp_evr_ge(a pulp_evr_t, b pulp_evr_t)
  RETURNS BOOLEAN as $$
  BEGIN
    return pulp_evr_cmp(a, b) >= 0;
  END;
$$ language 'plpgsql' IMMUTABLE;

-- Create operators
CREATE OPERATOR = (
  LEFTARG = pulp_evr_t,
  RIGHTARG = pulp_evr_t,
  FUNCTION = pulp_evr_eq,
  COMMUTATOR = =,
  NEGATOR = <>,
  RESTRICT = eqsel,
  JOIN = eqjoinsel,
  HASHES,
  MERGES
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
  RESTRICT = scalarlesel,
  JOIN = scalarlejoinsel
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

CREATE OPERATOR >= (
  LEFTARG = pulp_evr_t,
  RIGHTARG = pulp_evr_t,
  FUNCTION = pulp_evr_ge,
  COMMUTATOR = <=,
  NEGATOR = <,
  RESTRICT = scalargesel,
  JOIN = scalargejoinsel
);

-- Create operator class for btree indexing
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
             coalesce(version,''),
             coalesce(release,''))::pulp_evr_t
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
