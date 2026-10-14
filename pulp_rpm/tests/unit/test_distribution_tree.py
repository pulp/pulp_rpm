"""Regression tests for distribution tree subrepository cleanup."""

from django.test import TestCase

from pulpcore.plugin.models import Content, Domain

from pulp_rpm.app.models import DistributionTree, RpmRepository, Variant


def _create_distribution_tree(domain, suffix):
    return DistributionTree.objects.create(
        header_version="1.2",
        release_name="Shared subrepository test",
        release_short="TEST",
        release_version="1",
        arch="x86_64",
        build_timestamp=0.0,
        digest=f"shared-subrepo-tree-{suffix}",
        _pulp_domain=domain,
    )


def _create_variant(tree, repository):
    return Variant.objects.create(
        variant_id="Server",
        uid="Server",
        name="Server",
        type="variant",
        packages="Packages",
        distribution_tree=tree,
        repository=repository,
    )


class TestDistributionTree(TestCase):
    def test_has_subrepos_cleaned_up_on_delete(self):
        """DistributionTree's sharing the same subrepo can be deleted together."""
        domain, _ = Domain.objects.get_or_create(name="default")
        subrepo = RpmRepository.objects.create(
            name="shared-distribution-tree-subrepo", pulp_domain=domain, user_hidden=True
        )

        first_tree = _create_distribution_tree(domain, "first")
        second_tree = _create_distribution_tree(domain, "second")
        _create_variant(first_tree, subrepo)
        _create_variant(second_tree, subrepo)

        # Deleting together
        Content.objects.filter(pk__in=(first_tree.pk, second_tree.pk)).delete()
        self.assertFalse(RpmRepository.objects.filter(pk=subrepo.pk).exists())
        self.assertFalse(Variant.objects.filter(repository=subrepo).exists())

    def test_has_subrepos_cleaned_up_on_batched_delete(self):
        """DistributionTree's sharing the same subrepo can be deleted in batches."""
        domain, _ = Domain.objects.get_or_create(name="default")
        subrepo = RpmRepository.objects.create(
            name="shared-distribution-tree-subrepo", pulp_domain=domain, user_hidden=True
        )

        dt_1 = _create_distribution_tree(domain, "first")
        dt_2 = _create_distribution_tree(domain, "second")
        va_1 = _create_variant(dt_1, subrepo)
        va_2 = _create_variant(dt_2, subrepo)

        # This emulates an implementation of orphan cleanup, where it deletes Content in batches.
        # The case is when two DistributionTrees (DT) sharing a common Repository (R) through Variant (VA)
        # go into separate batches.
        #
        # Batch 1 - DT_1 cascade deletes VA_1 but skips R, as DT_2 still references it
        Content.objects.filter(pk=dt_1.pk).delete()
        self.assertTrue(RpmRepository.objects.filter(pk=subrepo.pk).exists())
        self.assertFalse(Variant.objects.filter(pk=va_1.pk).exists())
        self.assertTrue(Variant.objects.filter(pk=va_2.pk).exists())

        # Batch 2 - DT_2 cascade deletes VA_2 and R
        Content.objects.filter(pk=dt_2.pk).delete()
        self.assertFalse(RpmRepository.objects.filter(pk=subrepo.pk).exists())
        self.assertFalse(Variant.objects.filter(pk=va_2.pk).exists())
