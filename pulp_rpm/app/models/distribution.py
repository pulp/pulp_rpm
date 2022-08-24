from functools import reduce
from logging import getLogger

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from pulpcore.plugin.models import (
    Artifact,
    BaseModel,
    Content,
    ContentArtifact,
    Repository,
)

log = getLogger(__name__)


class DistributionTree(Content):
    """
    Model for an RPM distribution tree (also sometimes referenced as an installable tree).

    A distribution tree is described by a file in root of an RPM repository named either
    "treeinfo" or ".treeinfo". This INI file is used by system installers to boot from a URL.
    It describes the operating system or product contained in the distribution tree and
    where the bootable media is located for various platforms (where platform means
    'x86_64', 'xen', or similar).

    The description of the "treeinfo" format is included below, originally take from
    https://release-engineering.github.io/productmd/treeinfo-1.0.html

    Fields:
        header_version (Text):
            Metadata version
        release_name (Text):
            Release name
        release_short (Text):
            Release short name
        release_version (Text):
            Release version
        release_type (Text):
            Release type
        release_is_layered (Bool):
            Typically False for an operating system, True otherwise
        base_product_name (Text):
            Base product name
        base_product_short (Text):
            Base product short name
        base_product_version (Text):
            Base product *major* version
        base_product_type (Text):
            Base product release type
        arch (Text):
            Tree architecture
        build_timestamp (Float):
            Tree build time timestamp
        instimage (Text):
            Relative path to Anaconda instimage
        mainimage (Text):
            Relative path to Anaconda stage2 image
        discnum (Integer):
            Disc number
        totaldiscs (Integer):
            Number of discs in media set
        digest (Text):
            sha256 digest of the [.]treeinfo file

    """

    TYPE = "distribution_tree"

    header_version = models.CharField(max_length=10)

    release_name = models.CharField(max_length=50)
    release_short = models.CharField(max_length=50)
    release_version = models.CharField(max_length=10)
    release_is_layered = models.BooleanField(default=False)

    base_product_name = models.CharField(max_length=50, null=True)
    base_product_short = models.CharField(max_length=50, null=True)
    base_product_version = models.CharField(max_length=10, null=True)

    # tree
    arch = models.CharField(max_length=30)
    build_timestamp = models.FloatField()

    # stage2
    instimage = models.CharField(max_length=50, null=True)
    mainimage = models.CharField(max_length=50, null=True)

    # media
    discnum = models.IntegerField(null=True)
    totaldiscs = models.IntegerField(null=True)

    digest = models.CharField(max_length=64, null=False)

    def repositories(self):
        """
        Return the subrepos in this DistributionTree.

        Returns:
            django.db.models.QuerySet: Repos that are contained within this tree.

        """
        from pulp_rpm.app.models import RpmRepository

        repo_ids = list(self.addons.values_list("repository__pk", flat=True))
        repo_ids += list(self.variants.values_list("repository__pk", flat=True))
        return RpmRepository.objects.filter(pk__in=repo_ids)

    def content(self):
        """
        Return the subrepo content for this DistributionTree.

        Returns:
            django.db.models.QuerySet: Content that is contained within this tree.

        """
        if not self.repositories():
            return []

        version_content = [repo.latest_version().content for repo in self.repositories()]
        return reduce(lambda v1, v2: v1 | v2, version_content)

    def artifacts(self):
        """
        Return the subrepo artifacts for this DistributionTree.

        Returns:
            django.db.models.QuerySet: Content that is contained within this tree.

        """
        return Artifact.objects.filter(content__pk__in=self.content())

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("digest",)


class Checksum(BaseModel):
    """
    Distribution Tree Checksum.

    Checksums of selected files in a tree.

    Fields:
        path (Text):
            File path
        checksum (Text):
            Checksum value for the file

    Relations:

        distribution_tree (models.ForeignKey): The associated DistributionTree

    """

    path = models.CharField(max_length=128)
    checksum = models.CharField(max_length=128)
    distribution_tree = models.ForeignKey(
        DistributionTree, on_delete=models.CASCADE, related_name="checksums"
    )

    class Meta:
        unique_together = (
            "path",
            "checksum",
            "distribution_tree",
        )


class Image(BaseModel):
    """
    Distribution Tree Image.

    Images compatible with particular platform.

    Fields:
        name (Text):
            File name
        path (Text):
            File path
        platforms (Text):
            Compatible platforms

    Relations:

        distribution_tree (models.ForeignKey): The associated DistributionTree

    """

    name = models.CharField(max_length=50)
    path = models.CharField(max_length=128)
    platforms = models.CharField(max_length=20)
    distribution_tree = models.ForeignKey(
        DistributionTree, on_delete=models.CASCADE, related_name="images"
    )

    @property
    def artifact(self):
        """
        Returns artifact object.
        """
        content_artifact = ContentArtifact.objects.filter(
            content=self.distribution_tree,
            relative_path=self.path,
        ).first()

        artifact = content_artifact.artifact if content_artifact else None

        return artifact

    class Meta:
        unique_together = (
            "name",
            "path",
            "platforms",
            "distribution_tree",
        )


class Addon(BaseModel):
    """
    Distribution Tree Addon.

    Kickstart functionality expansion.

    Fields:
        addon_id (Text):
            Addon id
        uid (Text):
            Addon uid
        name (Text):
            Addon name
        type (Text):
            Addon type
        packages (Text):
            Relative path to directory with binary RPMs

    Relations:

        distribution_tree (models.ForeignKey): The associated DistributionTree
        repository (models.ForeignKey): The associated Repository

    """

    addon_id = models.CharField(max_length=50)
    uid = models.CharField(max_length=50)
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=20)
    packages = models.CharField(max_length=50)
    distribution_tree = models.ForeignKey(
        DistributionTree, on_delete=models.CASCADE, related_name="addons"
    )
    repository = models.ForeignKey(Repository, on_delete=models.PROTECT, related_name="addons")

    class Meta:
        unique_together = (
            "addon_id",
            "uid",
            "name",
            "type",
            "packages",
            "distribution_tree",
        )


class Variant(BaseModel):
    """
    Distribution Tree Variant.

    Fields:
        variant_id (Text):
            Variant id
        uid (Text):
            Variant uid
        name (Text):
            Variant name
        type (Text):
            Variant type
        packages (Text):
            Relative path to directory with binary RPMs
        source_packages (Text):
            Relative path to directory with source RPMs
        source_repository (Text):
            Relative path to YUM repository with source RPMs
        debug_packages (Text):
            Relative path to directory with debug RPMs
        debug_repository (Text):
            Relative path to YUM repository with debug RPMs
        identity (Text):
            Relative path to a pem file that identifies a product

    Relations:

        distribution_tree (models.ForeignKey): The associated DistributionTree
        repository (models.ForeignKey): The associated Repository. If it's a main repo ('.'),
                                        it's not set and a reference to a repository a distribution
                                        tree belongs to is implied.

    """

    variant_id = models.CharField(max_length=50)
    uid = models.CharField(max_length=50)
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=20)
    packages = models.CharField(max_length=50)
    source_packages = models.CharField(max_length=50, null=True)
    source_repository = models.CharField(max_length=50, null=True)
    debug_packages = models.CharField(max_length=50, null=True)
    debug_repository = models.CharField(max_length=50, null=True)
    identity = models.CharField(max_length=50, null=True)
    distribution_tree = models.ForeignKey(
        DistributionTree, on_delete=models.CASCADE, related_name="variants"
    )
    repository = models.ForeignKey(
        Repository, on_delete=models.PROTECT, related_name="variants", null=True
    )

    class Meta:
        unique_together = (
            "variant_id",
            "uid",
            "name",
            "type",
            "packages",
            "distribution_tree",
        )


@receiver(post_delete, sender=Addon)
@receiver(post_delete, sender=Variant)
def cleanup_subrepos(sender, instance, **kwargs):
    """
    Remove subrepos when a DistributionTree is being removed.

    """
    subrepo = None
    try:
        subrepo = instance.repository
    except Repository.DoesNotExist:
        pass
    if subrepo:
        Variant.objects.filter(repository=subrepo).delete()
        Addon.objects.filter(repository=subrepo).delete()
        subrepo.delete()
