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
        """DistributionTree's sharing the same subrepo can be deleted toghether."""
        domain, _ = Domain.objects.get_or_create(name="default")
        subrepo = RpmRepository.objects.create(
            name="shared-distribution-tree-subrepo", pulp_domain=domain, user_hidden=True
        )

        first_tree = _create_distribution_tree(domain, "first")
        second_tree = _create_distribution_tree(domain, "second")
        _create_variant(first_tree, subrepo)
        _create_variant(second_tree, subrepo)

        # Deleting toghether
        Content.objects.filter(pk__in=(first_tree.pk, second_tree.pk)).delete()
        self.assertFalse(RpmRepository.objects.filter(pk=subrepo.pk).exists())
        self.assertFalse(Variant.objects.filter(repository=subrepo).exists())

    def test_has_subrepos_cleaned_up_on_batched_delete(self):
        """DistributionTree's sharing the same subrepo can be deleted in batches."""
        domain, _ = Domain.objects.get_or_create(name="default")
        subrepo = RpmRepository.objects.create(
            name="shared-distribution-tree-subrepo", pulp_domain=domain, user_hidden=True
        )

        first_tree = _create_distribution_tree(domain, "first")
        second_tree = _create_distribution_tree(domain, "second")
        _create_variant(first_tree, subrepo)
        _create_variant(second_tree, subrepo)

        # Emulated batch 1
        Content.objects.filter(pk=first_tree.pk).delete()
        self.assertTrue(RpmRepository.objects.filter(pk=subrepo.pk).exists())
        self.assertFalse(
            Variant.objects.filter(distribution_tree=first_tree, repository=subrepo).exists()
        )
        self.assertTrue(
            Variant.objects.filter(distribution_tree=second_tree, repository=subrepo).exists()
        )

        # Emulated batch 2
        Content.objects.filter(pk=second_tree.pk).delete()
        self.assertFalse(RpmRepository.objects.filter(pk=subrepo.pk).exists())
