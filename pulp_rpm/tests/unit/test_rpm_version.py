"""
Unit tests for RPM version comparison functionality.
"""

from pulp_rpm.app.rpm_version import (
    RpmVersion,
    _compare_rpm_versions,
    _compare_version_strings,
    from_evr,
)


class TestRpmVersionComparison:
    """Test basic RPM version comparison functionality."""

    def test_evr_tostr(self):
        """Test that EVRs are printed as expected."""
        evr = RpmVersion("", "1.2.3", "45")
        assert str(evr) == "1.2.3-45"

        evr = RpmVersion("0", "1.2.3", "45")
        assert str(evr) == "0:1.2.3-45"

    def test_evr_parse(self):
        """Test that a correctly formed EVR string is parsed correctly."""
        evr = RpmVersion.from_string("1.2.3-45")
        expected = RpmVersion("", "1.2.3", "45")
        assert evr == expected

        evr = RpmVersion.from_string("0:1.2.3-45")
        expected = RpmVersion("0", "1.2.3", "45")
        assert evr == expected

        evr = RpmVersion.from_string("1:2.3.4-5")
        expected = RpmVersion("1", "2.3.4", "5")
        assert evr == expected

    def test_evr_parse_edge_cases(self):
        """Test that various not-well-formed EVR strings still get parsed in a sensible way."""
        assert from_evr("-") == ("", "", "")
        assert from_evr(".") == ("", ".", "")
        assert from_evr(":") == ("", "", "")
        assert from_evr(":-") == ("", "", "")
        assert from_evr(".-") == ("", ".", "")
        assert from_evr("0") == ("", "0", "")
        assert from_evr("0-") == ("", "0", "")
        assert from_evr(":0") == ("", "0", "")
        assert from_evr(":0-") == ("", "0", "")
        assert from_evr("0:") == ("0", "", "")
        assert from_evr("asdf:") == ("asdf", "", "")
        assert from_evr("~:") == ("~", "", "")

    def test_rpm_evr_compare(self):
        """Test direct comparison of rpm EVR strings."""
        assert _compare_rpm_versions("0:1.2.3-45", "1.2.3-45") == 0
        assert _compare_rpm_versions("1.2.3-45", "1:1.2.3-45") < 0
        assert _compare_rpm_versions("1.2.3-46", "1.2.3-45") > 0

    def test_evr_ord(self):
        """Test comparing EVRs using comparison operators."""
        # compare the same EVR without epoch as equal
        evr1 = RpmVersion.from_string("1.2.3-45")
        evr2 = RpmVersion.from_string("1.2.3-45")
        assert evr1 == evr2

        # compare the same EVR with epoch as equal
        evr1 = RpmVersion.from_string("2:1.2.3-45")
        evr2 = RpmVersion.from_string("2:1.2.3-45")
        assert evr1 == evr2

        # compare the same EVR with zero-epoch as equal to default-epoch
        evr1 = RpmVersion.from_string("1.2.3-45")
        evr2 = RpmVersion.from_string("0:1.2.3-45")
        assert evr1 == evr2

        # compare EVR with higher epoch and same version / release
        evr1 = RpmVersion.from_string("1.2.3-45")
        evr2 = RpmVersion.from_string("1:1.2.3-45")
        assert evr1 < evr2

        # compare EVR with higher epoch taken over EVR with higher version
        evr1 = RpmVersion.from_string("4.2.3-45")
        evr2 = RpmVersion.from_string("1:1.2.3-45")
        assert evr1 < evr2

        # compare EVR with higher version
        evr1 = RpmVersion.from_string("1.2.3-45")
        evr2 = RpmVersion.from_string("1.2.4-45")
        assert evr1 < evr2

        # compare EVR with higher version
        evr1 = RpmVersion.from_string("1.23.3-45")
        evr2 = RpmVersion.from_string("1.2.3-45")
        assert evr1 > evr2

        # compare EVR with higher version
        evr1 = RpmVersion.from_string("12.2.3-45")
        evr2 = RpmVersion.from_string("1.2.3-45")
        assert evr1 > evr2

        # compare EVR with higher version
        evr1 = RpmVersion.from_string("1.2.3-45")
        evr2 = RpmVersion.from_string("1.12.3-45")
        assert evr1 < evr2

        # compare versions with tilde parsing as older
        evr1 = RpmVersion.from_string("~1.2.3-45")
        evr2 = RpmVersion.from_string("1.2.3-45")
        assert evr1 < evr2

        # compare versions with tilde parsing as older
        evr1 = RpmVersion.from_string("~12.2.3-45")
        evr2 = RpmVersion.from_string("1.2.3-45")
        assert evr1 < evr2

        # compare versions with tilde parsing as older
        evr1 = RpmVersion.from_string("~12.2.3-45")
        evr2 = RpmVersion.from_string("~1.2.3-45")
        assert evr1 > evr2

        # compare versions with tilde parsing as older
        evr1 = RpmVersion.from_string("~3:12.2.3-45")
        evr2 = RpmVersion.from_string("0:1.2.3-45")
        assert evr1 < evr2

        # compare release
        evr1 = RpmVersion.from_string("1.2.3-45")
        evr2 = RpmVersion.from_string("1.2.3-46")
        assert evr1 < evr2

        # compare release
        evr1 = RpmVersion.from_string("1.2.3-45.fc39")
        evr2 = RpmVersion.from_string("1.2.3-46.fc38")
        assert evr1 < evr2

        # compare release
        evr1 = RpmVersion.from_string("1.2.3-3")
        evr2 = RpmVersion.from_string("1.2.3-10")
        assert evr1 < evr2

        # compare release
        evr1 = RpmVersion.from_string("1.2.3-3.fc40")
        evr2 = RpmVersion.from_string("1.2.3-10.fc39")
        assert evr1 < evr2

    def test_compare_version_string(self):
        """Test many different combinations of version string comparison behavior."""
        assert _compare_version_strings("1.0", "1.0") == 0
        assert _compare_version_strings("1.0", "2.0") < 0
        assert _compare_version_strings("2.0", "1.0") > 0

        assert _compare_version_strings("2.0.1", "2.0.1") == 0
        assert _compare_version_strings("2.0", "2.0.1") < 0
        assert _compare_version_strings("2.0.1", "2.0") > 0

        assert _compare_version_strings("5.0.1", "5.0.1a") < 0
        assert _compare_version_strings("5.0.1a", "5.0.1") > 0

        assert _compare_version_strings("5.0.a1", "5.0.a1") == 0
        assert _compare_version_strings("5.0.1a", "5.0.1a") == 0
        assert _compare_version_strings("5.0.a1", "5.0.a2") < 0
        assert _compare_version_strings("5.0.a2", "5.0.a1") > 0

        assert _compare_version_strings("10abc", "10.1abc") < 0
        assert _compare_version_strings("10.1abc", "10abc") > 0

        assert _compare_version_strings("8.0", "8.0.rc1") < 0
        assert _compare_version_strings("8.0.rc1", "8.0") > 0

        assert _compare_version_strings("10b2", "10a1") > 0
        assert _compare_version_strings("10a2", "10b2") < 0

        assert _compare_version_strings("6.6p1", "7.5p1") < 0
        assert _compare_version_strings("7.5p1", "6.6p1") > 0

        assert _compare_version_strings("6.5p1", "6.5p1") == 0
        assert _compare_version_strings("6.5p1", "6.5p2") < 0
        assert _compare_version_strings("6.5p2", "6.5p1") > 0
        assert _compare_version_strings("6.5p2", "6.6p1") < 0
        assert _compare_version_strings("6.6p1", "6.5p2") > 0

        assert _compare_version_strings("6.5p10", "6.5p10") == 0
        assert _compare_version_strings("6.5p1", "6.5p10") < 0
        assert _compare_version_strings("6.5p10", "6.5p1") > 0

        assert _compare_version_strings("abc10", "abc10") == 0
        assert _compare_version_strings("abc10", "abc10.1") < 0
        assert _compare_version_strings("abc10.1", "abc10") > 0

        assert _compare_version_strings("abc.4", "abc.4") == 0
        assert _compare_version_strings("abc.4", "8") < 0
        assert _compare_version_strings("8", "abc.4") > 0
        assert _compare_version_strings("abc.4", "2") < 0
        assert _compare_version_strings("2", "abc.4") > 0

        assert _compare_version_strings("1.0aa", "1.0aa") == 0
        assert _compare_version_strings("1.0a", "1.0aa") < 0
        assert _compare_version_strings("1.0aa", "1.0a") > 0

    def test_version_comparison_numeric_handling(self):
        """Test handling of numeric-like values in version strings."""
        assert _compare_version_strings("10.0001", "10.0001") == 0
        # sequences of leading zeroes are meant to be ignored - it's not *actually* treated
        # like a numeric value
        assert _compare_version_strings("10.0001", "10.1") == 0
        assert _compare_version_strings("10.1", "10.0001") == 0
        assert _compare_version_strings("10.0001", "10.0039") < 0
        assert _compare_version_strings("10.0039", "10.0001") > 0
        # but sequences of zeroes within a numeric segment are not ignored
        assert _compare_version_strings("10.1", "10.10001") < 0
        assert _compare_version_strings("10.1111", "10.10001") < 0
        assert _compare_version_strings("10.11111", "10.10001") > 0

        assert _compare_version_strings("20240521", "20240521") == 0
        assert _compare_version_strings("20240521", "20240522") < 0
        assert _compare_version_strings("20240522", "20240521") > 0
        assert _compare_version_strings("20240521", "202405210") < 0

    def test_version_comparison_tilde_and_caret(self):
        """Test behavior of tilde and caret operators."""
        assert _compare_version_strings("1.0~rc1", "1.0~rc1") == 0
        assert _compare_version_strings("1.0~rc1", "1.0") < 0
        assert _compare_version_strings("1.0", "1.0~rc1") > 0
        assert _compare_version_strings("1.0~rc1", "1.0~rc2") < 0
        assert _compare_version_strings("1.0~rc2", "1.0~rc1") > 0
        assert _compare_version_strings("1.0~rc1~git123", "1.0~rc1~git123") == 0
        assert _compare_version_strings("1.0~rc1~git123", "1.0~rc1") < 0
        assert _compare_version_strings("1.0~rc1", "1.0~rc1~git123") > 0

        assert _compare_version_strings("1.0^", "1.0^") == 0
        assert _compare_version_strings("1.0", "1.0^") < 0
        assert _compare_version_strings("1.0^", "1.0") > 0

        assert _compare_version_strings("1.0", "1.0git1^") < 0
        assert _compare_version_strings("1.0^git1", "1.0^git2") < 0
        assert _compare_version_strings("1.01", "1.0^git1") > 0
        assert _compare_version_strings("1.0^20240501", "1.0^20240501") == 0
        assert _compare_version_strings("1.0^20240501", "1.0.1") < 0
        assert _compare_version_strings("1.0^20240501^git1", "1.0^20240501^git1") == 0
        assert _compare_version_strings("1.0^20240502", "1.0^20240501^git1") > 0
        assert _compare_version_strings("1.0~rc1^git1", "1.0~rc1^git1") == 0
        assert _compare_version_strings("1.0~rc1", "1.0~rc1^git1") < 0
        assert _compare_version_strings("1.0~rc1^git1", "1.0~rc1") > 0
        assert _compare_version_strings("1.0^git1~pre", "1.0^git1~pre") == 0
        assert _compare_version_strings("1.0^git1~pre", "1.0^git1") < 0
        assert _compare_version_strings("1.0^git1", "1.0^git1~pre") > 0

    def test_non_intuitive_comparison_behavior(self):
        """Test some version comparison behavior that is a bit non-intuitive."""
        # (but needs to be maintained for compatibility)
        assert _compare_version_strings("1e.fc33", "1.fc33") < 0
        assert _compare_version_strings("1g.fc33", "1.fc33") > 0

    def test_non_alphanumeric_equivalence(self):
        """Test handling of non-alphanumeric ascii characters (excluding separators)."""
        # the existence of sequences of non-alphanumeric characters should not impact
        # the version comparison at all
        assert _compare_version_strings("b", "b") == 0
        assert _compare_version_strings("b+", "b+") == 0
        assert _compare_version_strings("b+", "b_") == 0
        assert _compare_version_strings("b_", "b+") == 0
        assert _compare_version_strings("+b", "+b") == 0
        assert _compare_version_strings("+b", "_b") == 0
        assert _compare_version_strings("_b", "+b") == 0

        assert _compare_version_strings("+b", "++b") == 0
        assert _compare_version_strings("+b", "+b+") == 0

        assert _compare_version_strings("+.", "+_") == 0
        assert _compare_version_strings("_+", "+.") == 0
        assert _compare_version_strings("+", ".") == 0
        assert _compare_version_strings(",", "+") == 0

        assert _compare_version_strings("++", "_") == 0
        assert _compare_version_strings("+", "..") == 0

        assert _compare_version_strings("4_0", "4_0") == 0
        assert _compare_version_strings("4_0", "4.0") == 0
        assert _compare_version_strings("4.0", "4_0") == 0

        assert _compare_version_strings("4.999", "5.0") < 0
        assert _compare_version_strings("4.999.9", "5.0") < 0
        assert _compare_version_strings("5.0", "4.999_9") > 0

        # except when it comes to breaking up sequences of alphanumeric characters
        # that do impact the comparison
        assert _compare_version_strings("4.999", "4.999.9") < 0
        assert _compare_version_strings("4.999", "4.99.9") > 0

    def test_non_ascii_character_equivalence(self):
        """Test handling of non-ascii characters."""
        # the existence of sequences of non-ascii characters should not impact the
        # version comparison at all
        assert _compare_version_strings("1.1.Á.1", "1.1.1") == 0
        assert _compare_version_strings("1.1.Á", "1.1.Á") == 0
        assert _compare_version_strings("1.1.Á", "1.1.Ê") == 0
        assert _compare_version_strings("1.1.ÁÁ", "1.1.Á") == 0
        assert _compare_version_strings("1.1.Á", "1.1.ÊÊ") == 0

        # except when it comes to breaking up sequences of ascii characters that do
        # impact the comparison
        assert _compare_version_strings("1.1Á1", "1.11") < 0
