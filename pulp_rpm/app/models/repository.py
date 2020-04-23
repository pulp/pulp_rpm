from logging import getLogger

from django.contrib.postgres.fields import JSONField
from django.db import (
    models,
    transaction,
)

from pulpcore.plugin.models import (
    AsciiArmoredDetachedSigningService,
    CreatedResource,
    Remote,
    Repository,
    RepositoryVersion,
    Publication,
    PublicationDistribution,
    Task,
)
from pulpcore.plugin.repo_version_utils import remove_duplicates, validate_repo_version

from pulp_rpm.app.constants import CHECKSUM_CHOICES
from pulp_rpm.app.models import (
    DistributionTree,
    Package,
    PackageCategory,
    PackageGroup,
    PackageEnvironment,
    PackageLangpacks,
    RepoMetadataFile,
    Modulemd,
    ModulemdDefaults,
    UpdateRecord,
)

log = getLogger(__name__)


class RpmRepository(Repository):
    """
    Repository for "rpm" content.

    Fields:

        sub_repo (Boolean):
            Whether is sub_repo or not
        last_sync_revision_number (Text):
            The revision number
        last_sync_remote (Remote):
            The remote used for the last sync
        last_sync_repo_version (Integer):
            The repo version number of the last sync
        original_checksum_types (JSON):
            Checksum for each metadata type
    """

    TYPE = "rpm"
    CONTENT_TYPES = [
        Package, UpdateRecord,
        PackageCategory, PackageGroup, PackageEnvironment, PackageLangpacks,
        RepoMetadataFile, DistributionTree,
        Modulemd, ModulemdDefaults
    ]

    metadata_signing_service = models.ForeignKey(
        AsciiArmoredDetachedSigningService,
        on_delete=models.SET_NULL,
        null=True
    )
    sub_repo = models.BooleanField(default=False)
    last_sync_revision_number = models.CharField(max_length=20)
    last_sync_remote = models.ForeignKey(Remote, null=True, on_delete=models.SET_NULL)
    last_sync_repo_version = models.PositiveIntegerField(default=0)
    original_checksum_types = JSONField(default=dict)

    def new_version(self, base_version=None):
        """
        Create a new RepositoryVersion for this Repository.

        Creation of a RepositoryVersion should be done in a RQ Job.

        Args:
            repository (pulpcore.app.models.Repository): to create a new version of
            base_version (pulpcore.app.models.RepositoryVersion): an optional repository version
                whose content will be used as the set of content for the new version

        Returns:
            pulpcore.app.models.RepositoryVersion: The Created RepositoryVersion

        """
        with transaction.atomic():
            version = RepositoryVersion(
                repository=self,
                number=int(self.next_version),
                base_version=base_version)
            version.save()

            if base_version:
                # first remove the content that isn't in the base version
                version.remove_content(version.content.exclude(pk__in=base_version.content))
                # now add any content that's in the base_version but not in version
                version.add_content(base_version.content.exclude(pk__in=version.content))

            if Task.current() and not self.sub_repo:
                resource = CreatedResource(content_object=version)
                resource.save()
            return version

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

    def finalize_new_version(self, new_version):
        """
        Ensure there are no duplicates in a repo version and content is not broken.

        Remove duplicates based on repo_key_fields.
        Ensure that modulemd is added with all its RPMs.
        Ensure that modulemd is removed with all its RPMs.
        Resolve advisory conflicts when there is more than one advisory with the same id.

        Args:
            new_version (pulpcore.app.models.RepositoryVersion): The incomplete RepositoryVersion to
                finalize.
        """
        if new_version.base_version:
            previous_version = new_version.base_version
        else:
            try:
                previous_version = new_version.previous()
            except RepositoryVersion.DoesNotExist:
                previous_version = None

        remove_duplicates(new_version)

        from pulp_rpm.app.modulemd import resolve_module_packages  # avoid circular import
        resolve_module_packages(new_version, previous_version)

        from pulp_rpm.app.advisory import resolve_advisories  # avoid circular import
        resolve_advisories(new_version, previous_version)
        validate_repo_version(new_version)


class RpmRemote(Remote):
    """
    Remote for "rpm" content.
    """

    TYPE = 'rpm'

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class RpmPublication(Publication):
    """
    Publication for "rpm" content.
    """

    TYPE = 'rpm'
    metadata_checksum_type = models.CharField(choices=CHECKSUM_CHOICES, max_length=10)
    package_checksum_type = models.CharField(choices=CHECKSUM_CHOICES, max_length=10)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class RpmDistribution(PublicationDistribution):
    """
    Distribution for "rpm" content.
    """

    TYPE = 'rpm'

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
