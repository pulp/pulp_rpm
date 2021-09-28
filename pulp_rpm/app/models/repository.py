import textwrap

from gettext import gettext as _
from logging import getLogger

from aiohttp.web_response import Response
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models, transaction
from pulpcore.plugin.download import DownloaderFactory
from pulpcore.plugin.models import (
    Artifact,
    AsciiArmoredDetachedSigningService,
    Content,
    CreatedResource,
    Remote,
    Repository,
    RepositoryVersion,
    Publication,
    Distribution,
    Task,
)
from pulpcore.plugin.repo_version_utils import (
    remove_duplicates,
    validate_duplicate_content,
    validate_version_paths,
)

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

from pulp_rpm.app.downloaders import RpmDownloader, RpmFileDownloader, UlnDownloader
from pulp_rpm.app.exceptions import DistributionTreeConflict
from pulp_rpm.app.shared_utils import urlpath_sanitize

log = getLogger(__name__)


class RpmRemote(Remote):
    """
    Remote for "rpm" content.
    """

    TYPE = "rpm"
    sles_auth_token = models.CharField(max_length=512, null=True)

    DEFAULT_DOWNLOAD_CONCURRENCY = 7
    DEFAULT_MAX_RETRIES = 4

    @property
    def download_factory(self):
        """
        Return the DownloaderFactory which can be used to generate asyncio capable downloaders.

        Returns:
            DownloadFactory: The instantiated DownloaderFactory to be used by
                get_downloader()

        """
        try:
            return self._download_factory
        except AttributeError:
            self._download_factory = DownloaderFactory(
                self,
                downloader_overrides={
                    "http": RpmDownloader,
                    "https": RpmDownloader,
                    "file": RpmFileDownloader,
                },
            )
            return self._download_factory

    def get_downloader(self, remote_artifact=None, url=None, **kwargs):
        """
        Get a downloader from either a RemoteArtifact or URL that is configured with this Remote.

        This method accepts either `remote_artifact` or `url` but not both. At least one is
        required. If neither or both are passed a ValueError is raised.

        Args:
            remote_artifact (:class:`~pulpcore.app.models.RemoteArtifact`): The RemoteArtifact to
                download.
            url (str): The URL to download.
            kwargs (dict): This accepts the parameters of
                :class:`~pulpcore.plugin.download.BaseDownloader`.
        Raises:
            ValueError: If neither remote_artifact and url are passed, or if both are passed.
        Returns:
            subclass of :class:`~pulpcore.plugin.download.BaseDownloader`: A downloader that
            is configured with the remote settings.

        """
        if self.sles_auth_token:
            kwargs["sles_auth_token"] = self.sles_auth_token
        return super().get_downloader(remote_artifact=remote_artifact, url=url, **kwargs)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class UlnRemote(Remote):
    """
    Remote for "uln" content.
    """

    TYPE = "uln"
    uln_server_base_url = models.CharField(max_length=512, null=True)

    @property
    def download_factory(self):
        """
        Return the DownloaderFactory which can be used to generate asyncio capable downloaders.

        Returns:
            DownloadFactory: The instantiated DownloaderFactory to be used by
                get_downloader()

        """
        try:
            return self._download_factory
        except AttributeError:
            self._download_factory = DownloaderFactory(
                self,
                downloader_overrides={
                    "uln": UlnDownloader,
                },
            )
            self._download_factory._handler_map["uln"] = self._download_factory._http_or_https
            return self._download_factory

    def get_downloader(self, remote_artifact=None, url=None, **kwargs):
        """
        Get a downloader from either a RemoteArtifact or URL that is configured with this Remote.

        This method accepts either `remote_artifact` or `url` but not both. At least one is
        required. If neither or both are passed a ValueError is raised.

        Args:
            remote_artifact (:class:`~pulpcore.app.models.RemoteArtifact`): The RemoteArtifact to
                download.
            url (str): The URL to download. Can be a ULN url.
            kwargs (dict): This accepts the parameters of
                :class:`~pulpcore.plugin.download.BaseDownloader`.
        Raises:
            ValueError: If neither remote_artifact and url are passed, or if both are passed.
        Returns:
            subclass of :class:`~pulpcore.plugin.download.BaseDownloader`: A downloader that
            is configured with the remote settings.

        """
        if self.uln_server_base_url:
            uln_server_base_url = self.uln_server_base_url
        else:
            uln_server_base_url = settings.DEFAULT_ULN_SERVER_BASE_URL

        return super().get_downloader(
            remote_artifact=remote_artifact,
            url=url,
            username=self.username,
            password=self.password,
            uln_server_base_url=uln_server_base_url,
            **kwargs,
        )

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


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
        last_sync_repomd_checksum (Text):
            The repo version repomd.xml file sha256
        original_checksum_types (JSON):
            Checksum for each metadata type
    """

    TYPE = "rpm"
    CONTENT_TYPES = [
        Package,
        UpdateRecord,
        PackageCategory,
        PackageGroup,
        PackageEnvironment,
        PackageLangpacks,
        RepoMetadataFile,
        DistributionTree,
        Modulemd,
        ModulemdDefaults,
    ]
    REMOTE_TYPES = [RpmRemote, UlnRemote]
    GPGCHECK_CHOICES = [(0, 0), (1, 1)]

    metadata_signing_service = models.ForeignKey(
        AsciiArmoredDetachedSigningService, on_delete=models.SET_NULL, null=True
    )
    sub_repo = models.BooleanField(default=False)
    last_sync_revision_number = models.CharField(max_length=20, null=True)
    last_sync_remote = models.ForeignKey(Remote, null=True, on_delete=models.SET_NULL)
    last_sync_repo_version = models.PositiveIntegerField(default=0)
    last_sync_repomd_checksum = models.CharField(max_length=64, null=True)
    original_checksum_types = JSONField(default=dict)
    retain_package_versions = models.PositiveIntegerField(default=0)

    autopublish = models.BooleanField(default=False)
    metadata_checksum_type = models.CharField(null=True, choices=CHECKSUM_CHOICES, max_length=10)
    package_checksum_type = models.CharField(null=True, choices=CHECKSUM_CHOICES, max_length=10)
    gpgcheck = models.IntegerField(default=0, choices=GPGCHECK_CHOICES)
    repo_gpgcheck = models.IntegerField(default=0, choices=GPGCHECK_CHOICES)
    sqlite_metadata = models.BooleanField(default=False)

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
            latest_version = self.versions.latest()
            if not latest_version.complete:
                latest_version.delete()

            version = RepositoryVersion(
                repository=self, number=int(self.next_version), base_version=base_version
            )
            version.save()

            if base_version:
                # first remove the content that isn't in the base version
                version.remove_content(version.content.exclude(pk__in=base_version.content))
                # now add any content that's in the base_version but not in version
                version.add_content(base_version.content.exclude(pk__in=version.content))

            if Task.current() and not self.sub_repo:
                resource = CreatedResource(content_object=version)
                resource.save()

            self.invalidate_cache()

            return version

    def on_new_version(self, version):
        """
        Called when new repository versions are created.

        Args:
            version: The new repository version.
        """
        super().on_new_version(version)

        # avoid circular import issues
        from pulp_rpm.app import tasks

        if self.autopublish:
            tasks.publish(
                repository_version_pk=version.pk,
                gpgcheck_options={"gpgcheck": self.gpgcheck, "repo_gpgcheck": self.repo_gpgcheck},
                metadata_signing_service=self.metadata_signing_service,
                checksum_types={
                    "metadata": self.metadata_checksum_type,
                    "package": self.package_checksum_type,
                },
                sqlite_metadata=self.sqlite_metadata,
            )

    @staticmethod
    def artifacts_for_version(version):
        """
        Return the artifacts for an RpmRepository version.

        Override the default behavior to include DistributionTree artifacts from nested repos.

        Args:
            version (pulpcore.app.models.RepositoryVersion): to get the artifacts for

        Returns:
            django.db.models.QuerySet: The artifacts that are contained within this version.

        """
        qs = Artifact.objects.filter(content__pk__in=version.content)
        for tree in DistributionTree.objects.filter(pk__in=version.content):
            qs |= tree.artifacts()

        return qs

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
            new_version (pulpcore.app.models.RepositoryVersion): The incomplete RepositoryVersion
                to finalize.
        """
        if new_version.base_version:
            previous_version = new_version.base_version
        else:
            try:
                previous_version = new_version.previous()
            except RepositoryVersion.DoesNotExist:
                previous_version = None

        remove_duplicates(new_version)
        self._resolve_distribution_trees(new_version, previous_version)

        from pulp_rpm.app.modulemd import resolve_module_packages  # avoid circular import

        resolve_module_packages(new_version, previous_version)

        self._apply_retention_policy(new_version)

        from pulp_rpm.app.advisory import resolve_advisories  # avoid circular import

        resolve_advisories(new_version, previous_version)

        #
        # Some repositories are odd. A given NEVRA with different checksums can appear at
        # different locations in the repo, or a single Artifact can be referenced by more than one
        # name.
        #
        # validate_duplicate_content() takes repo-keys into account - so same-NEVRA, diff-location
        # passes the test.
        #
        # The validate_version_paths() test checks for different-nevras, but same relative-path,
        # and raises an exception. Because of these odd repositories, this can't be fatal - so
        # we warn about it, but continue. At publish, we will have to pick one.
        validate_duplicate_content(new_version)
        try:
            validate_version_paths(new_version)
        except ValueError as ve:
            log.warning(
                _(
                    "New version of repository {repo} reports duplicate/overlap errors : "
                    "{value_errors}"
                ).format(repo=new_version.repository.name, value_errors=str(ve))
            )

    def _apply_retention_policy(self, new_version):
        """Apply the repository's "retain_package_versions" settings to the new version.

        Remove all non-modular packages that are older than the retention policy. A value of 0
        for the package retention policy represents disabled. A value of 3 would mean that the
        3 most recent versions of each package would be kept while older versions are discarded.

        Args:
            new_version (models.RepositoryVersion): Repository version to filter
        """
        assert (
            not new_version.complete
        ), "Cannot apply retention policy to completed repository versions"

        if self.retain_package_versions > 0:
            # It would be more ideal if, instead of annotating with an age and filtering manually,
            # we could use Django to filter the particular Package content we want to delete.
            # Something like ".filter(F('age') > self.retain_package_versions)" would be better
            # however this is not currently possible with Django. It would be possible with raw
            # SQL but the repository version content membership subquery is currently
            # django-managed and would be difficult to share.
            #
            # Instead we have to do the filtering manually.
            nonmodular_packages = (
                Package.objects.with_age()
                .filter(
                    pk__in=new_version.content.filter(pulp_type=Package.get_pulp_type()),
                    is_modular=False,  # don't want to filter out modular RPMs
                )
                .only("pk")
            )

            old_packages = []
            for package in nonmodular_packages:
                if package.age > self.retain_package_versions:
                    old_packages.append(package.pk)

            new_version.remove_content(Content.objects.filter(pk__in=old_packages))

    def _resolve_distribution_trees(self, new_version, previous_version):
        """
        There can be only one distribution tree in a repo version.

        Args:
            version (pulpcore.app.models.RepositoryVersion): current incomplete repository version
            previous_version (pulpcore.app.models.RepositoryVersion):  a version preceding
                                                                       the current incomplete one
        """
        disttree_pulp_type = DistributionTree.get_pulp_type()
        current_disttrees = new_version.content.filter(pulp_type=disttree_pulp_type)

        if len(current_disttrees) < 2:
            return

        if previous_version:
            previous_disttree = previous_version.content.get(pulp_type=disttree_pulp_type)
            new_version.remove_content(Content.objects.filter(pk=previous_disttree.pk))

        incoming_disttrees = new_version.content.filter(pulp_type=disttree_pulp_type)
        if len(incoming_disttrees) != 1:
            raise DistributionTreeConflict(
                _("More than one distribution tree cannot be added to a " "repository version.")
            )


class RpmPublication(Publication):
    """
    Publication for "rpm" content.
    """

    GPGCHECK_CHOICES = [(0, 0), (1, 1)]

    TYPE = "rpm"
    metadata_checksum_type = models.CharField(choices=CHECKSUM_CHOICES, max_length=10)
    package_checksum_type = models.CharField(choices=CHECKSUM_CHOICES, max_length=10)
    gpgcheck = models.IntegerField(default=0, choices=GPGCHECK_CHOICES)
    repo_gpgcheck = models.IntegerField(default=0, choices=GPGCHECK_CHOICES)
    sqlite_metadata = models.BooleanField(default=False)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class RpmDistribution(Distribution):
    """
    Distribution for "rpm" content.
    """

    TYPE = "rpm"
    SERVE_FROM_PUBLICATION = True
    repository_config_file_name = "config.repo"

    def content_handler(self, path):
        """Serve config.repo and repomd.xml.key."""
        if path == self.repository_config_file_name:
            repository, publication = self.get_repository_and_publication()
            if not publication:
                return
            base_url = "{}/".format(
                urlpath_sanitize(
                    settings.CONTENT_ORIGIN, settings.CONTENT_PATH_PREFIX, self.base_path
                )
            )
            val = textwrap.dedent(
                f"""\
                [{self.name}]
                name={self.name}
                enabled=1
                baseurl={base_url}
                gpgcheck={publication.gpgcheck}
                repo_gpgcheck={publication.repo_gpgcheck}
                """
            )

            signing_service = repository.metadata_signing_service
            if signing_service:
                gpgkey_path = urlpath_sanitize(
                    base_url,
                    "/repodata/repomd.xml.key",
                )
                val += f"gpgkey={gpgkey_path}\n"

            return Response(body=val)

    def content_handler_list_directory(self, rel_path):
        """Return the extra dir entries."""
        retval = set()
        if rel_path == "":
            retval.add(self.repository_config_file_name)
        return retval

    def get_repository_and_publication(self):
        """Retrieves the repository and publication associated with this distribution if exists."""
        repository = publication = None
        if self.publication:
            publication = self.publication.cast()
            repository = publication.repository.cast()
        elif self.repository:
            repository = self.repository.cast()
            versions = repository.versions.all()
            publications = Publication.objects.filter(
                repository_version__in=versions, complete=True
            )
            try:
                publication = (
                    publications.select_related("repository_version")
                    .latest("repository_version", "pulp_created")
                    .cast()
                )
            except ObjectDoesNotExist:
                pass
        return repository, publication

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
