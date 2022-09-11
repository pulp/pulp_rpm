from gettext import gettext as _
import logging

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError as DRFValidationError

from pulpcore.plugin.actions import ModifyRepositoryActionMixin
from pulpcore.plugin.models import RepositoryVersion
from pulpcore.plugin.tasking import dispatch
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
)
from pulpcore.plugin.viewsets import (
    DistributionViewSet,
    NamedModelViewSet,
    OperationPostponedResponse,
    PublicationViewSet,
    RemoteViewSet,
    RepositoryVersionViewSet,
    RepositoryViewSet,
)

from pulp_rpm.app import tasks
from pulp_rpm.app.constants import SYNC_POLICIES
from pulp_rpm.app.models import (
    RpmDistribution,
    RpmPublication,
    RpmRemote,
    RpmRepository,
    UlnRemote,
)
from pulp_rpm.app.serializers import (
    CopySerializer,
    RpmDistributionSerializer,
    RpmPublicationSerializer,
    RpmRemoteSerializer,
    RpmRepositorySerializer,
    RpmRepositorySyncURLSerializer,
    UlnRemoteSerializer,
)


class RpmRepositoryViewSet(RepositoryViewSet, ModifyRepositoryActionMixin):
    """
    A ViewSet for RpmRepository.
    """

    endpoint_name = "rpm"
    queryset = RpmRepository.objects.exclude(user_hidden=True)
    serializer_class = RpmRepositorySerializer

    @extend_schema(
        description="Trigger an asynchronous task to sync RPM content.",
        summary="Sync from remote",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=RpmRepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Dispatches a sync task.
        """
        repository = self.get_object()
        serializer = RpmRepositorySyncURLSerializer(
            data=request.data, context={"request": request, "repository_pk": pk}
        )
        serializer.is_valid(raise_exception=True)
        remote = serializer.validated_data.get("remote", repository.remote)
        mirror = serializer.validated_data.get("mirror")
        sync_policy = serializer.validated_data.get("sync_policy")
        skip_types = serializer.validated_data.get("skip_types")
        optimize = serializer.validated_data.get("optimize")

        if not sync_policy:
            sync_policy = SYNC_POLICIES.ADDITIVE if not mirror else SYNC_POLICIES.MIRROR_COMPLETE

        # validate some invariants that involve repository-wide settings.
        if sync_policy in (SYNC_POLICIES.MIRROR_COMPLETE, SYNC_POLICIES.MIRROR_CONTENT_ONLY):
            err_msg = (
                "Cannot use '{}' in combination with a 'mirror_complete' or "
                "'mirror_content_only' sync policy."
            )
            if repository.retain_package_versions > 0:
                raise DRFValidationError(err_msg.format("retain_package_versions"))

        if sync_policy == SYNC_POLICIES.MIRROR_COMPLETE:
            err_msg = "Cannot use '{}' in combination with a 'mirror_complete' sync policy."
            if repository.autopublish:
                raise DRFValidationError(err_msg.format("autopublish"))
            if skip_types:
                raise DRFValidationError(err_msg.format("skip_types"))

        result = dispatch(
            tasks.synchronize,
            shared_resources=[remote],
            exclusive_resources=[repository],
            kwargs={
                "sync_policy": sync_policy,
                "remote_pk": str(remote.pk),
                "repository_pk": str(repository.pk),
                "skip_types": skip_types,
                "optimize": optimize,
            },
        )
        return OperationPostponedResponse(result, request)


class RpmRepositoryVersionViewSet(RepositoryVersionViewSet):
    """
    RpmRepositoryVersion represents a single rpm repository version.
    """

    parent_viewset = RpmRepositoryViewSet


class RpmRemoteViewSet(RemoteViewSet):
    """
    A ViewSet for RpmRemote.
    """

    endpoint_name = "rpm"
    queryset = RpmRemote.objects.all()
    serializer_class = RpmRemoteSerializer


class UlnRemoteViewSet(RemoteViewSet):
    """
    A ViewSet for UlnRemote.
    """

    endpoint_name = "uln"
    queryset = UlnRemote.objects.all()
    serializer_class = UlnRemoteSerializer


class RpmPublicationViewSet(PublicationViewSet):
    """
    ViewSet for Rpm Publications.
    """

    endpoint_name = "rpm"
    queryset = RpmPublication.objects.exclude(complete=False)
    serializer_class = RpmPublicationSerializer

    @extend_schema(
        description="Trigger an asynchronous task to create a new RPM content publication.",
        responses={202: AsyncOperationResponseSerializer},
    )
    def create(self, request):
        """
        Dispatches a publish task.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repository_version = serializer.validated_data.get("repository_version")
        repository = RpmRepository.objects.get(pk=repository_version.repository.pk)

        metadata_checksum_type = serializer.validated_data.get(
            "metadata_checksum_type", repository.metadata_checksum_type
        )
        package_checksum_type = serializer.validated_data.get(
            "package_checksum_type", repository.package_checksum_type
        )
        checksum_types = dict(
            metadata=metadata_checksum_type,
            package=package_checksum_type,
        )
        gpgcheck_options = dict(
            gpgcheck=serializer.validated_data.get("gpgcheck", repository.gpgcheck),
            repo_gpgcheck=serializer.validated_data.get("repo_gpgcheck", repository.repo_gpgcheck),
        )
        sqlite_metadata = serializer.validated_data.get(
            "sqlite_metadata", repository.sqlite_metadata
        )
        if sqlite_metadata:
            logging.getLogger("pulp_rpm.deprecation").info(
                "Support for sqlite metadata generation will be removed from a future release "
                "of pulp_rpm. See https://tinyurl.com/sqlite-removal for more details"
            )

        if repository.metadata_signing_service:
            signing_service_pk = repository.metadata_signing_service.pk
        else:
            signing_service_pk = None

        result = dispatch(
            tasks.publish,
            shared_resources=[repository_version.repository],
            kwargs={
                "repository_version_pk": repository_version.pk,
                "metadata_signing_service": signing_service_pk,
                "checksum_types": checksum_types,
                "gpgcheck_options": gpgcheck_options,
                "sqlite_metadata": sqlite_metadata,
            },
        )
        return OperationPostponedResponse(result, request)


class RpmDistributionViewSet(DistributionViewSet):
    """
    ViewSet for RPM Distributions.
    """

    endpoint_name = "rpm"
    queryset = RpmDistribution.objects.all()
    serializer_class = RpmDistributionSerializer


class CopyViewSet(viewsets.ViewSet):
    """
    ViewSet for Content Copy.
    """

    serializer_class = CopySerializer

    @extend_schema(
        description="Trigger an asynchronous task to copy RPM content"
        "from one repository into another, creating a new"
        "repository version.",
        summary="Copy content",
        operation_id="copy_content",
        request=CopySerializer,
        responses={202: AsyncOperationResponseSerializer},
    )
    def create(self, request):
        """Copy content."""
        serializer = CopySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        dependency_solving = serializer.validated_data["dependency_solving"]
        config = serializer.validated_data["config"]

        config, shared_repos, exclusive_repos = self._process_config(config)

        async_result = dispatch(
            tasks.copy_content,
            shared_resources=shared_repos,
            exclusive_resources=exclusive_repos,
            args=[config, dependency_solving],
            kwargs={},
        )
        return OperationPostponedResponse(async_result, request)

    def _process_config(self, config):
        """
        Change the hrefs into pks within config.

        This method also implicitly validates that the hrefs map to objects and it returns a list of
        repos so that the task can lock on them.
        """
        result = []
        # exclusive use of the destination repos is needed since new repository versions are being
        # created, but source repos can be accessed in a read-only fashion in parallel, so long
        # as there are no simultaneous modifications.
        shared_repos = []
        exclusive_repos = []

        for entry in config:
            r = dict()
            source_version = NamedModelViewSet().get_resource(
                entry["source_repo_version"], RepositoryVersion
            )
            dest_repo = NamedModelViewSet().get_resource(entry["dest_repo"], RpmRepository)
            r["source_repo_version"] = source_version.pk
            r["dest_repo"] = dest_repo.pk
            shared_repos.append(source_version.repository)
            exclusive_repos.append(dest_repo)

            if "dest_base_version" in entry:
                try:
                    r["dest_base_version"] = dest_repo.versions.get(
                        number=entry["dest_base_version"]
                    ).pk
                except RepositoryVersion.DoesNotExist:
                    message = _(
                        "Version {version} does not exist for repository " "'{repo}'."
                    ).format(version=entry["dest_base_version"], repo=dest_repo.name)
                    raise DRFValidationError(detail=message)

            if entry.get("content") is not None:
                r["content"] = []
                for c in entry["content"]:
                    r["content"].append(NamedModelViewSet().extract_pk(c))
            result.append(r)

        return result, shared_repos, exclusive_repos
