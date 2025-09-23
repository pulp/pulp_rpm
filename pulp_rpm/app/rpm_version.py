# Sourced from https://github.com/nexB/univers
#
# Copyright (c) SAS Institute Inc.
# Copyright (c) Facebook, Inc. and its affiliates.
#
# SPDX-License-Identifier: MIT AND Apache-2.0
# Version comparison utility extracted from python-rpm-vercmp and further
# stripped down and significantly modified from the original at python-rpm-vercmp
# Also includes updates from Facebook antlir merged in.
#
# Visit https://aboutcode.org and https://github.com/nexB/univers for support and download.

# flake8: noqa

from typing import NamedTuple
from typing import Union


class RpmVersion(NamedTuple):
    """
    Represent an RPM version. It is ordered.
    """

    epoch: str
    version: str
    release: str

    def __str__(self, *args, **kwargs):
        return self.to_string()

    def to_string(self):
        if self.release:
            vr = f"{self.version}-{self.release}"
        else:
            vr = self.version

        if self.epoch:
            vr = f"{self.epoch}:{vr}"
        return vr

    @classmethod
    def from_string(cls, s):
        s.strip()
        e, v, r = from_evr(s)
        return cls(e, v, r)

    def __lt__(self, other):
        return _compare_rpm_versions(self, other) < 0

    def __gt__(self, other):
        return _compare_rpm_versions(self, other) > 0

    def __eq__(self, other):
        return _compare_rpm_versions(self, other) == 0

    def __le__(self, other):
        return _compare_rpm_versions(self, other) <= 0

    def __ge__(self, other):
        return _compare_rpm_versions(self, other) >= 0


def from_evr(s):
    """
    Return an (E, V, R) tuple given a string by splitting
    [e:]version-release into the three possible subcomponents.
    Default epoch, version and release to empty string if not specified.

    >>> assert from_evr("1:11.13.2.0-1") == ("1", "11.13.2.0", "1")
    >>> assert from_evr("11.13.2.0-1") == ("", "11.13.2.0", "1")
    """
    if ":" in s:
        e, _, vr = s.partition(":")
    else:
        e = ""
        vr = s

    if "-" in vr:
        v, _, r = vr.partition("-")
    else:
        v = vr
        r = ""
    return e, v, r


def _compare_rpm_versions(a: Union[RpmVersion, str], b: Union[RpmVersion, str]) -> int:
    """
    Compare two RPM versions ``a`` and ``b`` and return:
    -  1 if the version of a is newer than b
    -  0 if the versions match
    -  -1 if the version of a is older than b

    These are the legacy "cmp()" function semantics.

    This implementation is adapted from both this blog post:
    https://blog.jasonantman.com/2014/07/how-yum-and-rpm-compare-versions/
    and this Apache 2 licensed implementation:
    https://github.com/sassoftware/python-rpm-vercmp/blob/master/rpm_vercmp/vercmp.py

    For example::
    >>> assert compare_rpm_versions("1.0", "1.1") == -1
    >>> assert compare_rpm_versions("1.1", "1.0") == 1
    >>> assert compare_rpm_versions("11.13.2-1", "11.13.2.0-1") == -1
    >>> assert compare_rpm_versions("11.13.2.0-1", "11.13.2-1") == 1
    """
    if isinstance(a, str):
        a = RpmVersion.from_string(a)
    if isinstance(b, str):
        b = RpmVersion.from_string(b)
    if not isinstance(a, RpmVersion) and not isinstance(b, RpmVersion):
        raise TypeError(f"{a!r} and {b!r} must be RpmVersion or strings")

    a_epoch = a.epoch or "0"
    b_epoch = b.epoch or "0"

    # First compare the epoch, if set.  If the epoch's are not the same, then
    # the higher one wins no matter what the rest of the EVR is.
    if a_epoch != b_epoch:
        epoch_compare = _compare_version_strings(a_epoch, b_epoch)
        if epoch_compare != 0:
            return epoch_compare  # a > b

    # Epoch is the same, if version + release are the same we have a match
    if (a.version == b.version) and (a.release == b.release):
        return 0  # a == b

    # Compare version first, if version is equal then compare release
    version_compare = _compare_version_strings(a.version, b.version)
    if version_compare != 0:  # a > b || a < b
        return version_compare

    return _compare_version_strings(a.release, b.release)


# internal use: each individual component of the EVR is compared using this function
def _compare_version_strings(first, second):
    first = first.encode("utf-8")
    second = second.encode("utf-8")

    if first == second:
        return 0

    def not_alphanumeric_tilde_or_caret(c):
        return not (
            (ord(b"a") <= c <= ord(b"z"))
            or (ord(b"A") <= c <= ord(b"Z"))
            or (ord(b"0") <= c <= ord(b"9"))
            or c == ord(b"~")
            or c == ord(b"^")
        )

    def trim_start_matches(data, predicate):
        """Trim leading bytes that match the predicate"""
        start = 0
        while start < len(data) and predicate(data[start]):
            start += 1
        return data[start:]

    def strip_prefix(data, prefix):
        """Strip prefix from data, return (stripped_data, was_stripped)"""
        if data.startswith(prefix):
            return data[len(prefix) :], True
        return data, False

    def matching_contiguous(data, predicate):
        """Match contiguous characters that satisfy predicate"""
        if not data:
            return None, data

        if not predicate(data[0]):
            return None, data

        end = 0
        while end < len(data) and predicate(data[end]):
            end += 1

        return data[:end], data[end:]

    version1_part = first
    version2_part = second

    while True:
        # Strip any leading non-alphanumeric, non-tilde, non-caret characters
        version1_part = trim_start_matches(version1_part, not_alphanumeric_tilde_or_caret)
        version2_part = trim_start_matches(version2_part, not_alphanumeric_tilde_or_caret)

        # Tilde separator parses as "older" or lesser version
        version1_stripped, version1_had_tilde = strip_prefix(version1_part, b"~")
        version2_stripped, version2_had_tilde = strip_prefix(version2_part, b"~")

        if version1_had_tilde and not version2_had_tilde:
            return -1
        elif not version1_had_tilde and version2_had_tilde:
            return 1
        elif version1_had_tilde and version2_had_tilde:
            version1_part = version1_stripped
            version2_part = version2_stripped
            continue

        # Caret means the version is less... Unless the other version
        # has ended, then do the exact opposite.
        version1_stripped, version1_had_caret = strip_prefix(version1_part, b"^")
        version2_stripped, version2_had_caret = strip_prefix(version2_part, b"^")

        if version1_had_caret and not version2_had_caret:
            if not version2_part:  # second has ended
                return 1  # first > second
            else:  # second continues
                return -1  # first < second
        elif not version1_had_caret and version2_had_caret:
            if not version1_part:  # first has ended
                return -1  # first < second
            else:  # first continues
                return 1  # first > second
        elif version1_had_caret and version2_had_caret:
            version1_part = version1_stripped
            version2_part = version2_stripped
            continue

        # Check if we've run out of characters
        if not version1_part and not version2_part:
            return 0
        elif not version1_part:
            return -1
        elif not version2_part:
            return 1

        # Parse numeric or alphabetic segments
        def is_digit(c):
            return ord(b"0") <= c <= ord(b"9")

        def is_alpha(c):
            return (ord(b"a") <= c <= ord(b"z")) or (ord(b"A") <= c <= ord(b"Z"))

        if version1_part and is_digit(version1_part[0]):
            # First starts with digit - extract numeric segment
            segment1, version1_part = matching_contiguous(version1_part, is_digit)

            if version2_part and is_digit(version2_part[0]):
                # Both numeric
                segment2, version2_part = matching_contiguous(version2_part, is_digit)

                # Strip leading zeros
                segment1 = segment1.lstrip(b"0")
                segment2 = segment2.lstrip(b"0")

                # Compare by length first (more digits = larger number)
                if len(segment1) < len(segment2):
                    return -1
                elif len(segment1) > len(segment2):
                    return 1
                else:
                    # Same length, compare lexicographically
                    if segment1 < segment2:
                        return -1
                    elif segment1 > segment2:
                        return 1
                    # Equal, continue to next segment
            else:
                # First is numeric, second is not - numeric wins
                return 1
        else:
            # First starts with alpha or we're at end
            if version1_part:
                segment1, version1_part = matching_contiguous(version1_part, is_alpha)
            else:
                segment1 = b""

            if version2_part and is_digit(version2_part[0]):
                # First is alpha, second is numeric - numeric wins
                return -1
            else:
                # Both alpha or at least one is empty
                if version2_part:
                    segment2, version2_part = matching_contiguous(version2_part, is_alpha)
                else:
                    segment2 = b""

                # Compare alphabetically
                if segment1 < segment2:
                    return -1
                elif segment1 > segment2:
                    return 1
                # Equal, continue to next segment

    # Should not reach here due to the checks above, but just in case
    raise RuntimeError("somehow escaped the loop during version comparison")
