import os
import re
import textwrap
from gettext import gettext as _
from logging import getLogger

from aiohttp.web_response import Response
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from pulpcore.plugin.download import DownloaderFactory
from pulpcore.plugin.models import (
    Artifact,
    AsciiArmoredDetachedSigningService,
    AutoAddObjPermsMixin,
    Content,
    ContentArtifact,
    Distribution,
    Publication,
    Remote,
    RemoteArtifact,
    Repository,
    RepositoryContent,
    RepositoryVersion,
    PublishedMetadata,
)
from pulpcore.plugin.repo_version_utils import (
    remove_duplicates,
    validate_duplicate_content,
    validate_version_paths,
)

from pulp_rpm.app.constants import (
    CHECKSUM_CHOICES,
    COMPRESSION_CHOICES,
    LAYOUT_CHOICES,
)
from pulp_rpm.app.downloaders import RpmDownloader, RpmFileDownloader, UlnDownloader
from pulp_rpm.app.exceptions import DistributionTreeConflict
from pulp_rpm.app.models import (
    DistributionTree,
    Modulemd,
    ModulemdDefaults,
    ModulemdObsolete,
    Package,
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    PackageLangpacks,
    RepoMetadataFile,
    RpmPackageSigningService,
    UpdateRecord,
)
from pulp_rpm.app.shared_utils import urlpath_sanitize, annotate_with_age

log = getLogger(__name__)


class RpmRemote(Remote, AutoAddObjPermsMixin):
    """
    Remote for "rpm" content.
    """

    TYPE = "rpm"
    sles_auth_token = models.TextField(null=True)

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
        permissions = [
            ("manage_roles_rpmremote", "Can manage roles on an RPM remotes"),
        ]


class UlnRemote(Remote, AutoAddObjPermsMixin):
    """
    Remote for "uln" content.
    """

    TYPE = "uln"
    uln_server_base_url = models.TextField(null=True)

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
        permissions = [
            ("manage_roles_ulnremote", "Can manage roles on an ULN remotes"),
        ]


class RpmRepository(Repository, AutoAddObjPermsMixin):
    """
    Repository for "rpm" content.

    Fields:
        original_checksum_types (JSON): Checksum for each metadata type
        last_sync_details (JSON): Details about the last sync including repomd, settings used, etc.
        retain_package_versions (Integer): Max number of latest versions of each package to keep.
        autopublish (Boolean): Whether to automatically create a publication for new versions.
        metadata_checksum_type (String):
            The name of a checksum type to use for metadata when generating metadata.
        package_checksum_type (String):
            The name of a default checksum type to use for packages when generating metadata.
        package_signing_service (RpmPackageSigningService):
            Signing service to be used on package signing operations related to this repository.
        package_signing_fingerprint (String):
            The V4 fingerprint (160 bits) to be used by @package_signing_service.
        repo_config (JSON): repo configuration that will be served by distribution
        compression_type(pulp_rpm.app.constants.COMPRESSION_TYPES):
            Compression type to use for metadata files.
        layout(pulp_rpm.app.constants.LAYOUT_TYPES):
            How to layout the package files within the publication (flat, nested, etc.)
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
        ModulemdObsolete,
    ]
    REMOTE_TYPES = [RpmRemote, UlnRemote]

    metadata_signing_service = models.ForeignKey(
        AsciiArmoredDetachedSigningService, on_delete=models.SET_NULL, null=True
    )
    package_signing_service = models.ForeignKey(
        RpmPackageSigningService, on_delete=models.SET_NULL, null=True
    )
    package_signing_fingerprint = models.TextField(null=True, max_length=40)
    last_sync_details = models.JSONField(default=dict)
    retain_package_versions = models.PositiveIntegerField(default=0)

    autopublish = models.BooleanField(default=False)
    checksum_type = models.TextField(null=True, choices=CHECKSUM_CHOICES)
    compression_type = models.TextField(null=True, choices=COMPRESSION_CHOICES)
    layout = models.TextField(null=True, choices=LAYOUT_CHOICES)
    metadata_checksum_type = models.TextField(
        null=True, choices=CHECKSUM_CHOICES
    )  # DEPRECATED, remove in 3.31+
    package_checksum_type = models.TextField(
        null=True, choices=CHECKSUM_CHOICES
    )  # DEPRECATED, remove in 3.31+
    repo_config = models.JSONField(default=dict)

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
                metadata_signing_service=self.metadata_signing_service,
                checksum_type=self.checksum_type,
                repo_config=self.repo_config,
                compression_type=self.compression_type,
                layout=self.layout,
            )

    @property
    def published_metadata_size(self):
        versions = self.versions.all()
        publications = Publication.objects.filter(repository_version__in=versions, complete=True)
        published_metadata = PublishedMetadata.objects.filter(publication__in=publications)
        size = (
            Artifact.objects.filter(content__in=published_metadata)
            .distinct()
            .aggregate(size=models.Sum("size", default=0))["size"]
        )
        return size

    def all_content_pks(self):
        """Returns a list of pks for all content stored across all versions."""
        all_content = (
            RepositoryContent.objects.filter(repository=self)
            .distinct("content")
            .values_list("content")
        )
        repos = {self.pk}
        for dt in DistributionTree.objects.only().filter(pk__in=all_content):
            repos.update(dt.repositories().values_list("pk", flat=True))
        return (
            RepositoryContent.objects.filter(repository__in=repos)
            .distinct("content")
            .values_list("content")
        )

    @property
    def disk_size(self):
        """Returns the approximate size on disk for all artifacts stored across all versions."""
        return (
            Artifact.objects.filter(content__in=self.all_content_pks())
            .distinct()
            .aggregate(size=models.Sum("size", default=0))["size"]
        )

    @property
    def on_demand_size(self):
        """Returns the approximate size of all on-demand artifacts stored across all versions."""
        on_demand_ca = ContentArtifact.objects.filter(
            content__in=self.all_content_pks(), artifact=None
        )
        # Aggregate does not work with distinct("fields") so sum must be done manually
        ras = RemoteArtifact.objects.filter(
            content_artifact__in=on_demand_ca, size__isnull=False
        ).distinct("content_artifact")
        return sum(ras.values_list("size", flat=True))

    @staticmethod
    def on_demand_artifacts_for_version(version):
        """
        Returns the remote artifacts of on-demand content for a repository version.

        Override the default behavior to include DistributionTree artifacts from nested repos.
        Note: this only returns remote artifacts that have a non-null size.

        Args:
            version (pulpcore.app.models.RepositoryVersion): to get the remote artifacts for.
        Returns:
            django.db.models.QuerySet: The remote artifacts that are contained within this version.
        """
        content_pks = set(version.content.values_list("pk", flat=True))
        for tree in DistributionTree.objects.filter(pk__in=content_pks):
            content_pks.update(tree.content().values_list("pk", flat=True))
        on_demand_ca = ContentArtifact.objects.filter(content__in=content_pks, artifact=None)
        return RemoteArtifact.objects.filter(content_artifact__in=on_demand_ca, size__isnull=False)

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
        artifacts_pk = set(
            Artifact.objects.filter(content__pk__in=version.content).values_list(
                "pulp_id", flat=True
            )
        )
        for tree in DistributionTree.objects.filter(pk__in=version.content):
            artifacts_pk |= set(tree.artifacts().values_list("pulp_id", flat=True))

        return Artifact.objects.filter(pk__in=artifacts_pk)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [
            ("manage_roles_rpmrepository", "Can manage roles on RPM repositories"),
            ("modify_content_rpmrepository", "Add content to, or remove content from a repository"),
            ("repair_rpmrepository", "Copy a repository"),
            ("sync_rpmrepository", "Sync a repository"),
            ("delete_rpmrepository_version", "Delete a repository version"),
        ]

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
            nonmodular_packages = annotate_with_age(
                Package.objects.filter(
                    pk__in=new_version.content.filter(pulp_type=Package.get_pulp_type()),
                    is_modular=False,  # don't want to filter out modular RPMs
                ).only("pk")
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
            raise DistributionTreeConflict()


class RpmPublication(Publication, AutoAddObjPermsMixin):
    """
    Publication for "rpm" content.
    """

    TYPE = "rpm"
    checksum_type = models.TextField(choices=CHECKSUM_CHOICES)
    compression_type = models.TextField(null=True, choices=COMPRESSION_CHOICES)
    metadata_checksum_type = models.TextField(null=True, choices=CHECKSUM_CHOICES)
    package_checksum_type = models.TextField(null=True, choices=CHECKSUM_CHOICES)
    layout = models.TextField(null=True, choices=LAYOUT_CHOICES)
    repo_config = models.JSONField(default=dict)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [
            ("manage_roles_rpmpublication", "Can manage roles on an RPM publication"),
        ]


class RpmDistribution(Distribution, AutoAddObjPermsMixin):
    """
    Distribution for "rpm" content.
    """

    TYPE = "rpm"
    SERVE_FROM_PUBLICATION = True
    repository_config_file_name = "config.repo"
    INVALID_REPO_ID_CHARS = r"[^\w\-_.:]"

    generate_repo_config = models.BooleanField(default=False)

    def content_handler(self, path):
        """Serve config.repo and repomd.xml.key."""
        if self.generate_repo_config and path == self.repository_config_file_name:
            repository, publication = self.get_repository_and_publication()
            if not publication:
                return

            # "Where content will be retrieved from" comes first from CONTENT_ORIGIN.
            # If that's not set, use a specified baseurl.
            # If *that* isn't set - fail, we can't build a config.repo because we
            # don't have enough information to set the baseurl correctly.
            origin = (
                settings.CONTENT_ORIGIN
                if settings.CONTENT_ORIGIN
                else publication.repo_config.get("baseurl")
            )
            if not origin:
                return Response(
                    status=404,
                    reason=_(
                        "Cannot auto-generate config.repo when CONTENT_ORIGIN is not set and "
                        "no baseurl specified."
                    ),
                )
            if settings.DOMAIN_ENABLED:
                base_url = "{}/".format(
                    urlpath_sanitize(
                        origin,
                        settings.CONTENT_PATH_PREFIX,
                        self.pulp_domain.name,
                        self.base_path,
                    )
                )
            else:
                base_url = "{}/".format(
                    urlpath_sanitize(
                        origin,
                        settings.CONTENT_PATH_PREFIX,
                        self.base_path,
                    )
                )
            repo_config = publication.repo_config
            repo_config.pop("name", None)
            repo_config.pop("baseurl", None)
            val = textwrap.dedent(
                f"""\
                [{re.sub(self.INVALID_REPO_ID_CHARS, "", self.name)}]
                name={self.name}
                baseurl={base_url}
                """
            )
            for k, v in repo_config.items():
                val += f"{k}={v}\n"

            if "repo_gpgcheck" not in repo_config:
                val += "repo_gpgcheck=0\n"

            if "gpgcheck" not in repo_config:
                val += "gpgcheck=0\n"

            if "enabled" not in repo_config:
                val += "enabled=1\n"

            signing_service = repository.metadata_signing_service
            if signing_service:
                gpgkey_path = urlpath_sanitize(
                    base_url,
                    "/repodata/repomd.xml.key",
                )
                val += f"gpgkey={gpgkey_path}\n"

            return Response(body=val)

    def content_headers_for(self, path):
        """Return per-file http-headers."""
        headers = super().content_headers_for(path)
        base = os.path.basename(path)  # path.strip("/").split("/")[-1]
        if base in settings.NOCACHE_LIST:
            headers.update({"Cache-Control": "no-cache"})
        return headers

    def content_handler_list_directory(self, rel_path):
        """Return the extra dir entries."""
        retval = set()
        if self.generate_repo_config and rel_path == "":
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
        permissions = [
            ("manage_roles_rpmdistribution", "Can manage roles on an RPM distribution"),
        ]
