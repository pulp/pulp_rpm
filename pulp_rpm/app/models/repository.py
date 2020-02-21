from logging import getLogger

from django.db import (
    models,
    transaction,
)

from pulpcore.plugin.models import (
    CreatedResource,
    Remote,
    Repository,
    RepositoryVersion,
    Publication,
    PublicationDistribution,
    Task,
)
from pulpcore.plugin.repo_version_utils import remove_duplicates, validate_version_paths

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
    """

    TYPE = "rpm"
    CONTENT_TYPES = [
        Package, UpdateRecord,
        PackageCategory, PackageGroup, PackageEnvironment, PackageLangpacks,
        RepoMetadataFile, DistributionTree,
        Modulemd, ModulemdDefaults
    ]

    sub_repo = models.BooleanField(default=False)

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
            previous_version = RepositoryVersion.objects.filter(
                repository=self,
                number__lt=new_version.number,
                complete=True
            ).order_by('-number').first()

        remove_duplicates(new_version)
        validate_version_paths(new_version)

        from pulp_rpm.app.modulemd import resolve_module_packages  # avoid circular import
        resolve_module_packages(new_version, previous_version)

        from pulp_rpm.app.advisory import resolve_advisories  # avoid circular import
        resolve_advisories(new_version, previous_version)


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

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class RpmDistribution(PublicationDistribution):
    """
    Distribution for "rpm" content.
    """

    TYPE = 'rpm'

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
