"""
Unit tests for Package age calculation functionality.
"""

from django.test import TestCase

from pulp_rpm.app.models import Package
from pulp_rpm.app.shared_utils import annotate_with_age


class TestPackageAge(TestCase):
    """Test Package age calculation functionality."""

    def setUp(self):
        """Set up test packages with various version combinations."""
        # Package group 1: same name and arch, different versions
        self.pkg1_v1 = Package.objects.create(
            name="testpkg",
            epoch="0",
            version="1.0.0",
            release="1.el8",
            arch="x86_64",
            pkgId="checksum1",
            checksum_type="sha256",
        )

        self.pkg1_v2 = Package.objects.create(
            name="testpkg",
            epoch="0",
            version="2.0.0",
            release="1.el8",
            arch="x86_64",
            pkgId="checksum2",
            checksum_type="sha256",
        )

        self.pkg1_v3 = Package.objects.create(
            name="testpkg",
            epoch="0",
            version="1.5.0",
            release="2.el8",
            arch="x86_64",
            pkgId="checksum3",
            checksum_type="sha256",
        )

        # Package group 2: same name but different arch
        self.pkg2_i686 = Package.objects.create(
            name="testpkg",
            epoch="0",
            version="1.0.0",
            release="1.el8",
            arch="i686",
            pkgId="checksum4",
            checksum_type="sha256",
        )

        self.pkg2_i686_v2 = Package.objects.create(
            name="testpkg",
            epoch="0",
            version="3.0.0",
            release="1.el8",
            arch="i686",
            pkgId="checksum5",
            checksum_type="sha256",
        )

        # Package group 3: different name
        self.pkg3_other = Package.objects.create(
            name="otherpkg",
            epoch="0",
            version="1.0.0",
            release="1.el8",
            arch="x86_64",
            pkgId="checksum6",
            checksum_type="sha256",
        )

        # Package group 4: epoch differences
        self.pkg4_epoch0 = Package.objects.create(
            name="epochpkg",
            epoch="0",
            version="2.0.0",
            release="1.el8",
            arch="x86_64",
            pkgId="checksum7",
            checksum_type="sha256",
        )

        self.pkg4_epoch1 = Package.objects.create(
            name="epochpkg",
            epoch="1",
            version="1.0.0",
            release="1.el8",
            arch="x86_64",
            pkgId="checksum8",
            checksum_type="sha256",
        )

    def test_age_calculation_basic_versions(self):
        """Test that age is calculated correctly for basic version differences."""
        packages = annotate_with_age(
            Package.objects.filter(name="testpkg", arch="x86_64")
        ).order_by("age")

        # Expected order: 2.0.0 (age=1), 1.5.0-2 (age=2), 1.0.0 (age=3)
        self.assertEqual(packages.count(), 3)

        # Newest version should have age=1
        newest = packages[0]
        self.assertEqual(newest.version, "2.0.0")
        self.assertEqual(newest.age, 1)

        # Middle version should have age=2
        middle = packages[1]
        self.assertEqual(middle.version, "1.5.0")
        self.assertEqual(middle.release, "2.el8")
        self.assertEqual(middle.age, 2)

        # Oldest version should have age=3
        oldest = packages[2]
        self.assertEqual(oldest.version, "1.0.0")
        self.assertEqual(oldest.age, 3)

    def test_age_calculation_different_architectures(self):
        """Test that packages with different architectures are aged separately."""
        # x86_64 packages
        x86_packages = annotate_with_age(
            Package.objects.filter(name="testpkg", arch="x86_64")
        ).order_by("age")
        self.assertEqual(x86_packages.count(), 3)
        self.assertEqual(x86_packages[0].age, 1)  # 2.0.0
        self.assertEqual(x86_packages[1].age, 2)  # 1.5.0-2
        self.assertEqual(x86_packages[2].age, 3)  # 1.0.0

        # i686 packages
        i686_packages = annotate_with_age(
            Package.objects.filter(name="testpkg", arch="i686")
        ).order_by("age")
        self.assertEqual(i686_packages.count(), 2)

        # Even though i686 3.0.0 is newer than any x86_64 version, it should still have age=1
        # within its own architecture group
        self.assertEqual(i686_packages[0].version, "3.0.0")
        self.assertEqual(i686_packages[0].age, 1)
        self.assertEqual(i686_packages[1].version, "1.0.0")
        self.assertEqual(i686_packages[1].age, 2)

    def test_age_calculation_different_names(self):
        """Test that packages with different names are aged separately."""
        # Different package name should have its own age calculation
        other_packages = annotate_with_age(Package.objects.filter(name="otherpkg"))
        self.assertEqual(other_packages.count(), 1)
        self.assertEqual(other_packages[0].age, 1)

    def test_age_calculation_with_epochs(self):
        """Test that epoch is considered in age calculation."""
        epoch_packages = annotate_with_age(Package.objects.filter(name="epochpkg")).order_by("age")
        self.assertEqual(epoch_packages.count(), 2)

        # Epoch 1 should be newer than epoch 0, regardless of version numbers
        newest = epoch_packages[0]
        self.assertEqual(newest.epoch, "1")
        self.assertEqual(newest.version, "1.0.0")
        self.assertEqual(newest.age, 1)

        oldest = epoch_packages[1]
        self.assertEqual(oldest.epoch, "0")
        self.assertEqual(oldest.version, "2.0.0")
        self.assertEqual(oldest.age, 2)

    def test_age_all_packages(self):
        """Test age calculation when querying all packages."""
        all_packages = annotate_with_age(Package.objects.all())

        # Verify each package has an age
        for pkg in all_packages:
            self.assertIsNotNone(pkg.age)
            self.assertGreater(pkg.age, 0)

        # Check that packages are grouped correctly by name+arch
        testpkg_x86_ages = [
            p.age for p in all_packages if p.name == "testpkg" and p.arch == "x86_64"
        ]
        testpkg_i686_ages = [
            p.age for p in all_packages if p.name == "testpkg" and p.arch == "i686"
        ]
        otherpkg_ages = [p.age for p in all_packages if p.name == "otherpkg"]
        epochpkg_ages = [p.age for p in all_packages if p.name == "epochpkg"]

        self.assertEqual(sorted(testpkg_x86_ages), [1, 2, 3])
        self.assertEqual(sorted(testpkg_i686_ages), [1, 2])
        self.assertEqual(sorted(otherpkg_ages), [1])
        self.assertEqual(sorted(epochpkg_ages), [1, 2])

    def test_age_with_release_differences(self):
        """Test age calculation when versions are same but releases differ."""
        # Create packages with same version but different releases
        rel_pkg1 = Package.objects.create(  # noqa: F841
            name="relpkg",
            epoch="0",
            version="1.0.0",
            release="1.el8",
            arch="x86_64",
            pkgId="rel1",
            checksum_type="sha256",
        )

        rel_pkg2 = Package.objects.create(  # noqa: F841
            name="relpkg",
            epoch="0",
            version="1.0.0",
            release="2.el8",
            arch="x86_64",
            pkgId="rel2",
            checksum_type="sha256",
        )

        rel_pkg3 = Package.objects.create(  # noqa: F841
            name="relpkg",
            epoch="0",
            version="1.0.0",
            release="10.el8",
            arch="x86_64",
            pkgId="rel3",
            checksum_type="sha256",
        )

        packages = annotate_with_age(Package.objects.filter(name="relpkg")).order_by("age")

        # Expected order: 10.el8 > 2.el8 > 1.el8 (numeric comparison of release)
        self.assertEqual(packages[0].release, "10.el8")  # age=1
        self.assertEqual(packages[0].age, 1)

        self.assertEqual(packages[1].release, "2.el8")  # age=2
        self.assertEqual(packages[1].age, 2)

        self.assertEqual(packages[2].release, "1.el8")  # age=3
        self.assertEqual(packages[2].age, 3)

    def test_age_with_tilde_and_caret_versions(self):
        """Test age calculation with tilde and caret version characters."""
        # Create packages with tilde and caret versions
        Package.objects.create(
            name="tildepkg",
            epoch="0",
            version="1.0~rc1",
            release="1.el8",
            arch="x86_64",
            pkgId="tilde1",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="tildepkg",
            epoch="0",
            version="1.0",
            release="1.el8",
            arch="x86_64",
            pkgId="tilde2",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="tildepkg",
            epoch="0",
            version="1.0~rc2",
            release="1.el8",
            arch="x86_64",
            pkgId="tilde3",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="tildepkg",
            epoch="0",
            version="1.0^git123",
            release="1.el8",
            arch="x86_64",
            pkgId="tilde4",
            checksum_type="sha256",
        )

        packages = annotate_with_age(Package.objects.filter(name="tildepkg")).order_by("age")

        # Expected order: 1.0^git123 (age=1), 1.0 (age=2), 1.0~rc2 (age=3), 1.0~rc1 (age=4)
        # Caret sorts higher than regular, regular sorts higher than tilde
        self.assertEqual(packages[0].version, "1.0^git123")
        self.assertEqual(packages[0].age, 1)

        self.assertEqual(packages[1].version, "1.0")
        self.assertEqual(packages[1].age, 2)

        self.assertEqual(packages[2].version, "1.0~rc2")
        self.assertEqual(packages[2].age, 3)

        self.assertEqual(packages[3].version, "1.0~rc1")
        self.assertEqual(packages[3].age, 4)

    def test_age_with_numeric_handling_versions(self):
        """Test age calculation with numeric version handling edge cases."""
        # Create packages with leading zeros and numeric comparisons
        Package.objects.create(
            name="numpkg",
            epoch="0",
            version="10.0001",
            release="1.el8",
            arch="x86_64",
            pkgId="num1",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="numpkg",
            epoch="0",
            version="10.1",
            release="1.el8",
            arch="x86_64",
            pkgId="num2",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="numpkg",
            epoch="0",
            version="10.10001",
            release="1.el8",
            arch="x86_64",
            pkgId="num3",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="numpkg",
            epoch="0",
            version="20240521",
            release="1.el8",
            arch="x86_64",
            pkgId="num4",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="numpkg",
            epoch="0",
            version="202405210",
            release="1.el8",
            arch="x86_64",
            pkgId="num5",
            checksum_type="sha256",
        )

        packages = annotate_with_age(Package.objects.filter(name="numpkg")).order_by("age")

        # Expected order: 202405210 > 20240521 > 10.10001 > 10.1 == 10.0001
        # Leading zeros are ignored in numeric segments
        self.assertEqual(packages[0].version, "202405210")
        self.assertEqual(packages[0].age, 1)

        self.assertEqual(packages[1].version, "20240521")
        self.assertEqual(packages[1].age, 2)

        self.assertEqual(packages[2].version, "10.10001")
        self.assertEqual(packages[2].age, 3)

        # 10.1 and 10.0001 should be considered equal (leading zeros ignored)
        # but one will have age=4 and the other age=5 based on creation order
        remaining_versions = [packages[3].version, packages[4].version]
        self.assertIn("10.1", remaining_versions)
        self.assertIn("10.0001", remaining_versions)

    def test_age_with_non_intuitive_comparison_versions(self):
        """Test age calculation with non-intuitive version comparison behavior."""
        # Create packages that test the 'e' vs numeric behavior
        Package.objects.create(
            name="intuitivepkg",
            epoch="0",
            version="1e.fc33",
            release="1.el8",
            arch="x86_64",
            pkgId="intuit1",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="intuitivepkg",
            epoch="0",
            version="1.fc33",
            release="1.el8",
            arch="x86_64",
            pkgId="intuit2",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="intuitivepkg",
            epoch="0",
            version="1g.fc33",
            release="1.el8",
            arch="x86_64",
            pkgId="intuit3",
            checksum_type="sha256",
        )

        packages = annotate_with_age(Package.objects.filter(name="intuitivepkg")).order_by("age")

        # Expected order: 1g.fc33 > 1.fc33 > 1e.fc33
        # 'e' comes before numeric in comparison, 'g' comes after numeric
        self.assertEqual(packages[0].version, "1g.fc33")
        self.assertEqual(packages[0].age, 1)

        self.assertEqual(packages[1].version, "1.fc33")
        self.assertEqual(packages[1].age, 2)

        self.assertEqual(packages[2].version, "1e.fc33")
        self.assertEqual(packages[2].age, 3)

    def test_age_with_non_alphanumeric_equivalence_versions(self):
        """Test age calculation with non-alphanumeric character equivalence."""
        # Create packages with various non-alphanumeric separators
        Package.objects.create(
            name="alphapkg",
            epoch="0",
            version="4.0",
            release="1.el8",
            arch="x86_64",
            pkgId="alpha1",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="alphapkg",
            epoch="0",
            version="4_0",
            release="1.el8",
            arch="x86_64",
            pkgId="alpha2",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="alphapkg",
            epoch="0",
            version="4+0",
            release="1.el8",
            arch="x86_64",
            pkgId="alpha3",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="alphapkg",
            epoch="0",
            version="4.999",
            release="1.el8",
            arch="x86_64",
            pkgId="alpha4",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="alphapkg",
            epoch="0",
            version="4.999.9",
            release="1.el8",
            arch="x86_64",
            pkgId="alpha5",
            checksum_type="sha256",
        )

        packages = annotate_with_age(Package.objects.filter(name="alphapkg")).order_by("age")

        # Expected behavior: 4.999.9 > 4.999 > 4.0 == 4_0 == 4+0
        # Non-alphanumeric characters are treated as equivalent separators
        self.assertEqual(packages[0].version, "4.999.9")
        self.assertEqual(packages[0].age, 1)

        self.assertEqual(packages[1].version, "4.999")
        self.assertEqual(packages[1].age, 2)

        # The remaining three should be considered equivalent versions
        # but will have different ages based on creation order
        remaining_versions = [packages[2].version, packages[3].version, packages[4].version]
        self.assertIn("4.0", remaining_versions)
        self.assertIn("4_0", remaining_versions)
        self.assertIn("4+0", remaining_versions)

    def test_age_with_non_ascii_character_versions(self):
        """Test age calculation with non-ASCII character handling."""
        # Create packages with non-ASCII characters
        Package.objects.create(
            name="asciipkg",
            epoch="0",
            version="1.1.1",
            release="1.el8",
            arch="x86_64",
            pkgId="ascii1",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="asciipkg",
            epoch="0",
            version="1.1.Á.1",
            release="1.el8",
            arch="x86_64",
            pkgId="ascii2",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="asciipkg",
            epoch="0",
            version="1.11",
            release="1.el8",
            arch="x86_64",
            pkgId="ascii3",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="asciipkg",
            epoch="0",
            version="1.1Á1",
            release="1.el8",
            arch="x86_64",
            pkgId="ascii4",
            checksum_type="sha256",
        )

        packages = annotate_with_age(Package.objects.filter(name="asciipkg")).order_by("age")

        # Expected behavior: 1.11 > 1.1.1 == 1.1.Á.1 > 1.1Á1
        # Non-ASCII chars are ignored unless they break up alphanumeric sequences
        self.assertEqual(packages[0].version, "1.11")
        self.assertEqual(packages[0].age, 1)

        # 1.1.1 and 1.1.Á.1 should be equivalent
        equivalent_versions = [packages[1].version, packages[2].version]
        self.assertIn("1.1.1", equivalent_versions)
        self.assertIn("1.1.Á.1", equivalent_versions)

        # 1.1Á1 should be last (non-ASCII breaks up the sequence)
        self.assertEqual(packages[3].version, "1.1Á1")
        self.assertEqual(packages[3].age, 4)

    def test_age_with_mixed_scenarios(self):
        """Test age calculation with mixed version scenarios."""
        Package.objects.create(
            name="mixedpkg",
            epoch="0",
            version="2.0",
            release="1.el8",
            arch="x86_64",
            pkgId="mixed1",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="mixedpkg",
            epoch="0",
            version="2.0.rc1",
            release="1.el8",
            arch="x86_64",
            pkgId="mixed2",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="mixedpkg",
            epoch="0",
            version="2.0.0",
            release="1.el8",
            arch="x86_64",
            pkgId="mixed3",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="mixedpkg",
            epoch="1",
            version="1.0",
            release="1.el8",
            arch="x86_64",
            pkgId="mixed4",
            checksum_type="sha256",
        )

        packages = annotate_with_age(Package.objects.filter(name="mixedpkg")).order_by("age")

        # Expected order: 1:1.0 (epoch wins) > 2.0.0 > 2.0 > 2.0.rc1
        self.assertEqual(packages[0].epoch, "1")
        self.assertEqual(packages[0].version, "1.0")
        self.assertEqual(packages[0].age, 1)

        # Rest should be ordered by version comparison
        remaining = packages[1:]
        versions = [p.version for p in remaining]
        self.assertIn("2.0.0", versions)
        self.assertIn("2.0", versions)
        self.assertIn("2.0.rc1", versions)

    def test_age_with_filtered_queryset(self):
        """Test age calculation when applied to a filtered queryset."""
        # Create packages in database
        pkg1 = Package.objects.create(  # noqa: F841
            name="filterpkg",
            epoch="0",
            version="1.0",
            release="1.el8",
            arch="x86_64",
            pkgId="filter1",
            checksum_type="sha256",
        )

        pkg2 = Package.objects.create(  # noqa: F841
            name="filterpkg",
            epoch="0",
            version="2.0",
            release="1.el8",
            arch="x86_64",
            pkgId="filter2",
            checksum_type="sha256",
        )

        Package.objects.create(
            name="filterpkg",
            epoch="0",
            version="3.0",
            release="1.el8",
            arch="x86_64",
            pkgId="filter3",
            checksum_type="sha256",
        )

        # Test with filtered queryset (only older versions)
        filtered_packages = annotate_with_age(
            Package.objects.filter(name="filterpkg", version__in=["1.0", "2.0"])
        ).order_by("age")

        self.assertEqual(filtered_packages.count(), 2)
        # In the filtered set, 2.0 should be newest (age=1), 1.0 should be oldest (age=2)
        self.assertEqual(filtered_packages[0].version, "2.0")
        self.assertEqual(filtered_packages[0].age, 1)
        self.assertEqual(filtered_packages[1].version, "1.0")
        self.assertEqual(filtered_packages[1].age, 2)

    def test_age_with_empty_queryset(self):
        """Test age calculation with empty queryset."""
        empty_packages = annotate_with_age(Package.objects.filter(name="nonexistent"))
        self.assertEqual(len(empty_packages.all()), 0)

    def test_age_with_mixed_filtering_scenarios(self):
        """Test age calculation with various filtering scenarios that might cause bugs."""
        # Create packages across multiple groups
        for i in range(5):
            Package.objects.create(
                name="grouppkg",
                epoch="0",
                version=f"{i}.0",
                release="1.el8",
                arch="x86_64",
                pkgId=f"group{i}",
                checksum_type="sha256",
            )

        # Create another group
        for i in range(3):
            Package.objects.create(
                name="otherpkg",
                epoch="0",
                version=f"{i}.0",
                release="1.el8",
                arch="x86_64",
                pkgId=f"other{i}",
                checksum_type="sha256",
            )

        # Test 1: Filter to get partial group from first package set
        partial_group = annotate_with_age(
            Package.objects.filter(name="grouppkg", version__in=["2.0", "3.0", "4.0"])
        ).order_by("age")

        self.assertEqual(partial_group.count(), 3)
        # In this filtered set: 4.0 (age=1), 3.0 (age=2), 2.0 (age=3)
        self.assertEqual(partial_group[0].version, "4.0")
        self.assertEqual(partial_group[0].age, 1)
        self.assertEqual(partial_group[1].version, "3.0")
        self.assertEqual(partial_group[1].age, 2)
        self.assertEqual(partial_group[2].version, "2.0")
        self.assertEqual(partial_group[2].age, 3)

        # Test 2: Filter across multiple package groups
        cross_group = annotate_with_age(
            Package.objects.filter(name__in=["grouppkg", "otherpkg"], version="2.0")
        )

        # Should have one package from each group, both with age=1 in their respective groups
        for pkg in cross_group:
            self.assertEqual(pkg.version, "2.0")
            self.assertEqual(pkg.age, 1)  # Each is newest in its filtered group

    def test_age_consistency_with_retention_scenario(self):
        """Test age calculation in a scenario similar to how retention policies work"""
        packages_data = [
            ("retentiontestpkg", "1.0", "1.el8"),
            ("retentiontestpkg", "1.1", "1.el8"),
            ("retentiontestpkg", "1.2", "1.el8"),
            ("retentiontestpkg", "2.0", "1.el8"),
            ("retentiontestpkg", "2.1", "1.el8"),
        ]

        created_packages = []
        for i, (name, version, release) in enumerate(packages_data):
            pkg = Package.objects.create(
                name=name,
                epoch="0",
                version=version,
                release=release,
                arch="x86_64",
                pkgId=f"retention{i}",
                checksum_type="sha256",
            )
            created_packages.append(pkg)

        # Test: Get packages and apply age - this should match what retention logic does
        all_packages = annotate_with_age(Package.objects.filter(name="retentiontestpkg"))

        # Verify all packages have correct age values
        for pkg in all_packages:
            self.assertIsNotNone(pkg.age)
            self.assertGreater(pkg.age, 0)

        # Test different retention scenarios
        # Scenario 1: Keep only newest 2 versions (should remove 3 packages)
        oldest_packages = all_packages.filter(age__gt=2)
        self.assertEqual(oldest_packages.count(), 3)

        # Scenario 2: Keep only newest 3 versions (should remove 2 packages)
        oldest_packages = all_packages.filter(age__gt=3)
        self.assertEqual(oldest_packages.count(), 2)
