"""
Unit tests for Package with null EVR field.
"""

from django.test import TestCase

from pulp_rpm.app.models import Package


class TestPackageNullEvr(TestCase):
    """Test Package handling of null EVR field."""

    def test_package_creation_with_normal_evr_data(self):
        """Test that Package creation works with normal EVR data."""
        pkg = Package.objects.create(
            name="testpkg",
            epoch="0",
            version="1.0.0",
            release="1.el8",
            arch="x86_64",
            pkgId="checksum1",
            checksum_type="sha256",
        )

        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.name, "testpkg")
        self.assertEqual(pkg.version, "1.0.0")

    def test_package_with_empty_evr_strings(self):
        """Test Package creation with empty EVR strings."""
        pkg = Package.objects.create(
            name="minimal_pkg",
            epoch="",
            version="",
            release="",
            arch="noarch",
            pkgId="checksum_minimal",
            checksum_type="sha256",
        )

        self.assertIsNotNone(pkg)
        self.assertEqual(pkg.name, "minimal_pkg")
        self.assertEqual(pkg.arch, "noarch")
