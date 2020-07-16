from logging import getLogger

from django.db import (
    IntegrityError,
    models,
    transaction,
)

from pulpcore.plugin.models import (
    BaseModel,
    Content,
    ContentArtifact,
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
        repository_id(uuid):
            Id of a repository a DistributionTree belongs to. Each repository has its own
            DistributionTree, it cannot be shared.

    """

    TYPE = 'distribution_tree'

    header_version = models.CharField(max_length=10)

    release_name = models.CharField(max_length=50)
    release_short = models.CharField(max_length=20)
    release_version = models.CharField(max_length=10)
    release_is_layered = models.BooleanField(default=False)

    base_product_name = models.CharField(max_length=50, null=True)
    base_product_short = models.CharField(max_length=20, null=True)
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

    repository_id = models.UUIDField()

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = (
            "repository_id",
            "header_version",
            "release_name",
            "release_short",
            "release_version",
            "arch",
            "build_timestamp",
        )

    def get_copy(self, repository):
        """
        Create a copy of a distribution tree for a different repository.
        It does NOT copy content of the main repo.

        Args:
            repository(RpmRepository): a repository to create a copy for

        Returns:
            new_disttree: a copy of a distribution tree for a specified repository
        """
        with transaction.atomic():
            new_disttree = self
            new_disttree.pk = None
            new_disttree.pulp_id = None
            new_disttree.repository_id = repository.pk
            try:
                with transaction.atomic():
                    new_disttree.save()
            except IntegrityError:
                return __class__.objects.get(repository_id=new_disttree.repository_id,
                                             header_version=new_disttree.header_version,
                                             release_name=new_disttree.release_name,
                                             release_short=new_disttree.release_short,
                                             release_version=new_disttree.release_version,
                                             arch=new_disttree.arch,
                                             build_timestamp=new_disttree.build_timestamp)
            Checksum.copy(new_disttree)
            Image.copy(new_disttree)
            Addon.copy(new_disttree)
            Variant.copy(new_disttree)

        return new_disttree


class CopyDistTreeModelsMixin:
    """
    Mixin class providing the default method to copy auxiliary models for a DistributionTree.
    """
    def copy(self, disttree):
        """
        Create a copy of an object for a specified distribution tree which has a relation to it

        Args:
            disttree(DistributionTree): a distribution tree to create a copy for
        """
        new_obj = self
        self.pk = None
        self.pulp_id = None
        new_obj.distribution_tree = disttree
        try:
            with transaction.atomic():
                new_obj.save()
        except IntegrityError:
            pass
        else:
            return new_obj


class Checksum(BaseModel, CopyDistTreeModelsMixin):
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
    checksum = models.CharField(max_length=128, null=True)
    distribution_tree = models.ForeignKey(
        DistributionTree, on_delete=models.CASCADE, related_name='checksums'
    )

    class Meta:
        unique_together = (
            "path",
            "checksum",
            "distribution_tree",
        )


class Image(BaseModel, CopyDistTreeModelsMixin):
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

    name = models.CharField(max_length=20)
    path = models.CharField(max_length=128)
    platforms = models.CharField(max_length=20)
    distribution_tree = models.ForeignKey(
        DistributionTree, on_delete=models.CASCADE, related_name='images'
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


class Addon(BaseModel, CopyDistTreeModelsMixin):
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
        repository (models.ForeignKey): The associated RpmRepository

    """

    addon_id = models.CharField(max_length=50)
    uid = models.CharField(max_length=50)
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=20)
    packages = models.CharField(max_length=50)
    distribution_tree = models.ForeignKey(
        DistributionTree, on_delete=models.CASCADE, related_name='addons'
    )
    repository = models.ForeignKey(
        "RpmRepository", on_delete=models.PROTECT, related_name='addons'
    )

    class Meta:
        unique_together = (
            "addon_id",
            "uid",
            "name",
            "type",
            "packages",
            "distribution_tree",
        )


class Variant(BaseModel, CopyDistTreeModelsMixin):
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
        repository (models.ForeignKey): The associated RpmRepository

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
        DistributionTree, on_delete=models.CASCADE, related_name='variants'
    )
    repository = models.ForeignKey(
        "RpmRepository", on_delete=models.PROTECT, related_name='+'
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

    def copy(self, disttree):
        """
        Create a copy of a Variant for a specified distribution tree.

        It can be copied as any other auxiliary model except the case when a Variant is pointing
        to a main repository. In this case it should refer to a repository a distribution tree
        belongs to.

        Args:
            disttree(DistributionTree): a distribution tree to create a copy for

        """
        new_variant = super().copy(disttree)
        if new_variant and not self.repository.sub_repo:
            new_variant.repository_pk = disttree.repository_id
            new_variant.save()
