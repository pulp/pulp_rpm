# Adds a new 'evr_v2' column alongside the old 'evr' column.
# Dropping the old column to remain zero-downtime safe.
#
# The trigger is updated to maintain both columns simultaneously.
#
# == Why replace evr? ==
#
# The old evr column (pulp_evr_t) decomposed version strings into arrays of
# (numeric, text) tuples and relied on PostgreSQL's native array comparison.
# This cannot correctly handle tilde (~) or caret (^):
#
#   - Tilde must sort BEFORE end-of-string: 1.0~rc1 < 1.0
#     But PostgreSQL always sorts a shorter prefix-matching array as less-than
#     a longer one, so no element value can invert this.
#
#   - Caret must sort AFTER end-of-string but BEFORE any continuation segment:
#     1.0 < 1.0^git1 < 1.0.1
#     Same fundamental problem with array length comparison.
#
# == How evr_v2 works ==
#
# The evr_v2 column is a single BYTEA value encoding the entire EVR
# (epoch, version, release) as a sortable binary key. Native bytea comparison
# (memcmp-style, byte by byte) produces correct RPM version ordering per
# rpmvercmp(). The parsing logic mirrors RPM's rpmvercmp.cc.
#
# The key is structured as: [4-byte epoch] [version sortkey] [release sortkey]
#
# Epoch is encoded as a 4-byte big-endian unsigned integer. Because memcmp
# compares left-to-right, the epoch bytes are always compared first, and a
# higher epoch always dominates regardless of version/release — matching RPM
# semantics. NULL epochs are coalesced to 0.
#
# Each version/release sortkey uses five byte markers, chosen so their numeric
# order matches the required RPM sort order:
#
#   \x01  — tilde (~), sorts lowest, before end-of-version
#   \x02  — end-of-version (appended once at the end of the key)
#   \x03  — caret (^), sorts after end but before real segments
#   \x04  — alpha segment prefix (followed by the segment text + \x00 delimiter)
#   \x05  — numeric segment prefix (followed by length byte + digits + \x00)
#
# This order directly encodes the RPM rule: ~ < end < ^ < alpha < numeric.
#
# Segment encoding details:
#
#   Alpha segments: \x04 + raw ASCII text + \x00
#     Lexicographic byte comparison gives correct alphabetical ordering.
#
#   Numeric segments: \x05 + length_byte + stripped_digits + \x00
#     Leading zeros are stripped. The length byte sorts first, so longer digit
#     strings (= larger numbers) always sort after shorter ones. Within the
#     same length, digit characters compare lexicographically, which is correct
#     for same-length decimal integers.
#
# Each version/release component ends with \x02 (end-of-version). When two
# versions are equal, the comparison naturally falls through the end marker
# into the release bytes. This is why no separator is needed between the
# version and release sortkeys — the \x02 end marker serves as a delimiter.
#
# Example: EVR "2:1.0~rc1-3.fc40" encodes as:
#
#   epoch (4-byte big-endian):
#     \x00 \x00 \x00 \x02            — epoch 2
#
#   version sortkey ("1.0~rc1"):
#     \x05 \x01 1 \x00               — numeric segment "1"
#     \x05 \x01 0 \x00               — numeric segment "0"
#     \x01                            — tilde
#     \x04 rc \x00                    — alpha segment "rc"
#     \x05 \x01 1 \x00               — numeric segment "1"
#     \x02                            — end-of-version
#
#   release sortkey ("3.fc40"):
#     \x05 \x01 3 \x00               — numeric segment "3"
#     \x04 fc \x00                    — alpha segment "fc"
#     \x05 \x02 40 \x00              — numeric segment "40"
#     \x02                            — end-of-version
#
# Comparing "1.0~rc1" vs "1.0": after the shared prefix "1.0", the first key
# has \x01 (tilde) while the second has \x02 (end). Since \x01 < \x02,
# "1.0~rc1" correctly sorts before "1.0".

from django.db import migrations, models
from pulp_rpm.app.models.package import RpmVersionField

# The sort key function (version/release component)
extension_sql = """
CREATE OR REPLACE FUNCTION pulp_rpm_version_sortkey(ver TEXT)
RETURNS BYTEA AS $$
DECLARE
    pos INTEGER := 1;
    len INTEGER;
    ch TEXT;
    result BYTEA := ''::bytea;
    segment TEXT;
    seg_len INTEGER;
    stripped TEXT;
BEGIN
    IF ver IS NULL OR ver = '' THEN
        RETURN '\\x02'::bytea;
    END IF;

    len := length(ver);

    WHILE pos <= len LOOP
        -- Skip non-alphanumeric, non-tilde, non-caret characters
        LOOP
            IF pos > len THEN EXIT; END IF;
            ch := substr(ver, pos, 1);
            EXIT WHEN ch BETWEEN 'a' AND 'z'
                     OR ch BETWEEN 'A' AND 'Z'
                     OR ch BETWEEN '0' AND '9'
                     OR ch = '~'
                     OR ch = '^';
            pos := pos + 1;
        END LOOP;

        IF pos > len THEN EXIT; END IF;

        ch := substr(ver, pos, 1);

        -- Tilde sorts before everything, including end-of-version
        IF ch = '~' THEN
            result := result || '\\x01'::bytea;
            pos := pos + 1;
            CONTINUE;
        END IF;

        -- Caret sorts after end-of-version but before any real segment
        IF ch = '^' THEN
            result := result || '\\x03'::bytea;
            pos := pos + 1;
            CONTINUE;
        END IF;

        IF ch BETWEEN '0' AND '9' THEN
            -- Numeric segment
            segment := '';
            WHILE pos <= len AND substr(ver, pos, 1) BETWEEN '0' AND '9' LOOP
                segment := segment || substr(ver, pos, 1);
                pos := pos + 1;
            END LOOP;
            -- Strip leading zeros for numeric comparison
            stripped := ltrim(segment, '0');
            seg_len := length(stripped);
            -- Encode: type(\\x05) + length_byte + digits + delimiter(\\x00)
            result := result || '\\x05'::bytea
                             || set_byte('\\x00'::bytea, 0, seg_len)
                             || stripped::bytea
                             || '\\x00'::bytea;
        ELSE
            -- Alpha segment
            segment := '';
            WHILE pos <= len AND (
                substr(ver, pos, 1) BETWEEN 'a' AND 'z' OR
                substr(ver, pos, 1) BETWEEN 'A' AND 'Z'
            ) LOOP
                segment := segment || substr(ver, pos, 1);
                pos := pos + 1;
            END LOOP;
            -- Encode: type(\\x04) + segment + delimiter(\\x00)
            result := result || '\\x04'::bytea
                             || segment::bytea
                             || '\\x00'::bytea;
        END IF;
    END LOOP;

    -- End-of-version marker: sorts between tilde (\\x01) and caret (\\x03)
    result := result || '\\x02'::bytea;

    RETURN result;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION pulp_rpm_evr_sortkey(epoch_val TEXT, ver TEXT, rel TEXT)
RETURNS BYTEA AS $$
BEGIN
    RETURN int4send(coalesce(epoch_val::int, 0))
        || pulp_rpm_version_sortkey(coalesce(ver, ''))
        || pulp_rpm_version_sortkey(coalesce(rel, ''));
END;
$$ LANGUAGE plpgsql IMMUTABLE;
"""

# Add new column, populate it, make it NOT NULL
add_column_sql = """
ALTER TABLE rpm_package ADD COLUMN evr_v2 bytea;

UPDATE rpm_package SET evr_v2 = pulp_rpm_evr_sortkey(epoch, version, release);

ALTER TABLE rpm_package ALTER COLUMN evr_v2 SET NOT NULL;
"""

# Replace trigger to maintain BOTH old evr and new evr_v2
dual_trigger_sql = """
CREATE OR REPLACE FUNCTION pulp_evr_trigger() RETURNS trigger AS $$
BEGIN
    -- Maintain old evr column (for running services during deployment)
    NEW.evr = (select ROW(coalesce(NEW.epoch::numeric,0),
                          pulp_rpmver_array(coalesce(NEW.version,'pulp_isempty'))::pulp_evr_array_item[],
                          pulp_rpmver_array(coalesce(NEW.release,'pulp_isempty'))::pulp_evr_array_item[])::pulp_evr_t);
    -- Maintain new evr_v2 column
    NEW.evr_v2 = pulp_rpm_evr_sortkey(NEW.epoch, NEW.version, NEW.release);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('rpm', '0071_alter_rpmpublication_layout_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(extension_sql),
                migrations.RunSQL(add_column_sql),
                migrations.RunSQL(dual_trigger_sql),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='package',
                    name='evr',
                    field=RpmVersionField(db_column='evr_v2'),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name='package',
            index=models.Index(fields=['name', 'arch', 'evr'], name='rpm_package_name_5db9c5_idx'),
        ),
    ]
