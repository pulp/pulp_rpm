import os
from django_filters import CharFilter
from gettext import gettext as _

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.serializers import ValidationError as DRFValidationError

from pulpcore.plugin.models import PulpTemporaryFile
from pulpcore.plugin.actions import ModifyRepositoryActionMixin
from pulpcore.plugin.models import AlternateContentSourcePath, RepositoryVersion, TaskGroup
from pulpcore.plugin.tasking import dispatch
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    TaskGroupOperationResponseSerializer,
)
from pulpcore.plugin.viewsets import (
    AlternateContentSourceViewSet,
    DistributionViewSet,
    ContentFilter,
    NoArtifactContentUploadViewSet,
    NamedModelViewSet,
    OperationPostponedResponse,
    PublicationViewSet,
    ReadOnlyContentViewSet,
    RemoteViewSet,
    RepositoryViewSet,
    RepositoryVersionViewSet,
    SingleArtifactContentUploadViewSet,
    TaskGroupOperationResponse,
)

from pulp_rpm.app import tasks
from pulp_rpm.app.constants import SYNC_POLICIES
from pulp_rpm.app.models import (
    RpmAlternateContentSource,
    DistributionTree,
    Modulemd,
    ModulemdDefaults,
    Package,
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    PackageLangpacks,
    RepoMetadataFile,
    RpmDistribution,
    RpmRemote,
    UlnRemote,
    RpmRepository,
    RpmPublication,
    UpdateRecord,
)
from pulp_rpm.app.serializers import (
    RpmAlternateContentSourceSerializer,
    CopySerializer,
    CompsXmlSerializer,
    DistributionTreeSerializer,
    MinimalPackageSerializer,
    MinimalUpdateRecordSerializer,
    ModulemdDefaultsSerializer,
    ModulemdSerializer,
    PackageSerializer,
    PackageCategorySerializer,
    PackageEnvironmentSerializer,
    PackageGroupSerializer,
    PackageLangpacksSerializer,
    RepoMetadataFileSerializer,
    RpmDistributionSerializer,
    RpmRemoteSerializer,
    UlnRemoteSerializer,
    RpmRepositorySerializer,
    RpmRepositorySyncURLSerializer,
    RpmPublicationSerializer,
    UpdateRecordSerializer,
)


class PackageFilter(ContentFilter):
    """
    FilterSet for Package.
    """

    sha256 = CharFilter(field_name="_artifacts__sha256")

    class Meta:
        model = Package
        fields = {
            "name": ["exact", "in", "ne"],
            "epoch": ["exact", "in", "ne"],
            "version": ["exact", "in", "ne"],
            "release": ["exact", "in", "ne"],
            "arch": ["exact", "in", "ne"],
            "pkgId": ["exact", "in"],
            "checksum_type": ["exact", "in", "ne"],
        }


class PackageViewSet(SingleArtifactContentUploadViewSet):
    """
    A ViewSet for Package.

    Define endpoint name which will appear in the API endpoint for this content type.
    For example::
        http://pulp.example.com/pulp/api/v3/content/rpm/packages/

    Also specify queryset and serializer for Package.
    """

    endpoint_name = "packages"
    queryset = Package.objects.prefetch_related("_artifacts")
    serializer_class = PackageSerializer
    minimal_serializer_class = MinimalPackageSerializer
    filterset_class = PackageFilter


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


class UpdateRecordFilter(ContentFilter):
    """
    FilterSet for UpdateRecord.
    """

    class Meta:
        model = UpdateRecord
        fields = {
            "id": ["exact", "in"],
            "status": ["exact", "in", "ne"],
            "severity": ["exact", "in", "ne"],
            "type": ["exact", "in", "ne"],
        }


class UpdateRecordViewSet(NoArtifactContentUploadViewSet):
    """
    A ViewSet for UpdateRecord.

    Define endpoint name which will appear in the API endpoint for this content type.
    For example::
        http://pulp.example.com/pulp/api/v3/content/rpm/advisories/

    Also specify queryset and serializer for UpdateRecord.
    """

    endpoint_name = "advisories"
    queryset = UpdateRecord.objects.all()
    serializer_class = UpdateRecordSerializer
    minimal_serializer_class = MinimalUpdateRecordSerializer
    filterset_class = UpdateRecordFilter


class RpmPublicationViewSet(PublicationViewSet):
    """
    ViewSet for Rpm Publications.
    """

    endpoint_name = "rpm"
    queryset = RpmPublication.objects.exclude(complete=False)
    serializer_class = RpmPublicationSerializer

    @extend_schema(
        description="Trigger an asynchronous task to create a new RPM " "content publication.",
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


class PackageGroupViewSet(ReadOnlyContentViewSet):
    """
    PackageGroup ViewSet.
    """

    endpoint_name = "packagegroups"
    queryset = PackageGroup.objects.all()
    serializer_class = PackageGroupSerializer


class PackageCategoryViewSet(ReadOnlyContentViewSet):
    """
    PackageCategory ViewSet.
    """

    endpoint_name = "packagecategories"
    queryset = PackageCategory.objects.all()
    serializer_class = PackageCategorySerializer


class PackageEnvironmentViewSet(ReadOnlyContentViewSet):
    """
    PackageEnvironment ViewSet.
    """

    endpoint_name = "packageenvironments"
    queryset = PackageEnvironment.objects.all()
    serializer_class = PackageEnvironmentSerializer


class PackageLangpacksViewSet(ReadOnlyContentViewSet):
    """
    PackageLangpacks ViewSet.
    """

    endpoint_name = "packagelangpacks"
    queryset = PackageLangpacks.objects.all()
    serializer_class = PackageLangpacksSerializer


class DistributionTreeViewSet(ReadOnlyContentViewSet):
    """
    Distribution Tree Viewset.

    """

    endpoint_name = "distribution_trees"
    queryset = DistributionTree.objects.all()
    serializer_class = DistributionTreeSerializer


class RepoMetadataFileViewSet(ReadOnlyContentViewSet):
    """
    RepoMetadataFile Viewset.

    """

    endpoint_name = "repo_metadata_files"
    queryset = RepoMetadataFile.objects.all()
    serializer_class = RepoMetadataFileSerializer


class ModulemdFilter(ContentFilter):
    """
    FilterSet for Modulemd.
    """

    sha256 = CharFilter(field_name="_artifacts__sha256")

    class Meta:
        model = Modulemd
        fields = {
            "name": ["exact", "in"],
            "stream": ["exact", "in"],
        }


class ModulemdViewSet(SingleArtifactContentUploadViewSet):
    """
    ViewSet for Modulemd.
    """

    endpoint_name = "modulemds"
    queryset = Modulemd.objects.all()
    serializer_class = ModulemdSerializer
    filterset_class = ModulemdFilter


class ModulemdDefaultsFilter(ContentFilter):
    """
    FilterSet for ModulemdDefaults.
    """

    sha256 = CharFilter(field_name="_artifacts__sha256")

    class Meta:
        model = ModulemdDefaults
        fields = {
            "module": ["exact", "in"],
            "stream": ["exact", "in"],
        }


class ModulemdDefaultsViewSet(SingleArtifactContentUploadViewSet):
    """
    ViewSet for Modulemd.
    """

    endpoint_name = "modulemd_defaults"
    queryset = ModulemdDefaults.objects.all()
    serializer_class = ModulemdDefaultsSerializer
    filterset_class = ModulemdDefaultsFilter


class CompsXmlViewSet(viewsets.ViewSet):
    """
    ViewSet for comps.xml Upload.
    """

    @extend_schema(
        description="Trigger an asynchronous task to upload a comps.xml file.",
        summary="Upload comps.xml",
        operation_id="rpm_comps_upload",
        request=CompsXmlSerializer,
        responses={202: AsyncOperationResponseSerializer},
    )
    def create(self, request):
        """Upload a comps.xml file and create Content from it."""
        serializer = CompsXmlSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        # Store TemporaryUpload as a file we can find/use from our task
        task_payload = {k: v for k, v in request.data.items()}
        file_content = task_payload.pop("file", None)
        temp_file = PulpTemporaryFile.init_and_validate(file_content)
        temp_file.save()

        # Lock destination-repo if we are given one so two uploads can't collide
        repository = serializer.validated_data.get("repository", None)
        repo_pk = str(repository.pk) if repository else None
        replace = serializer.validated_data.get("replace", False)

        # Kick off task to Do the Deed
        task = dispatch(
            tasks.upload_comps,
            exclusive_resources=[repository] if repository else [],
            args=([str(temp_file.pk), repo_pk, replace]),
            kwargs={},
        )
        return OperationPostponedResponse(task, request)


class RpmAlternateContentSourceViewSet(AlternateContentSourceViewSet):
    """
    ViewSet for ACS.
    """

    endpoint_name = "rpm"
    queryset = RpmAlternateContentSource.objects.all()
    serializer_class = RpmAlternateContentSourceSerializer

    @extend_schema(
        description="Trigger an asynchronous task to create Alternate Content Source content.",
        responses={202: TaskGroupOperationResponseSerializer},
    )
    @action(methods=["post"], detail=True)
    def refresh(self, request, pk):
        """
        Refresh ACS metadata.
        """
        acs = get_object_or_404(RpmAlternateContentSource, pk=pk)
        acs_paths = AlternateContentSourcePath.objects.filter(alternate_content_source=pk)
        task_group = TaskGroup.objects.create(
            description=f"Refreshing {acs_paths.count()} alternate content source path(s)."
        )

        # Get required defaults for sync operation
        optimize = RpmRepositorySyncURLSerializer().data["optimize"]
        skip_types = RpmRepositorySyncURLSerializer().data["skip_types"]

        for acs_path in acs_paths:
            # Create or get repository for the path
            repo_data = {
                "name": f"{acs.name}--{acs_path.pk}--repository",
                "retain_repo_versions": 1,
                "user_hidden": True,
            }
            repo, created = RpmRepository.objects.get_or_create(**repo_data)
            if created:
                acs_path.repository = repo
                acs_path.save()
            acs_url = (
                os.path.join(acs.remote.url, acs_path.path) if acs_path.path else acs.remote.url
            )

            # Dispatching ACS path to own task and assign it to common TaskGroup
            dispatch(
                tasks.synchronize,
                shared_resources=[acs.remote, acs],
                task_group=task_group,
                kwargs={
                    "remote_pk": str(acs.remote.pk),
                    "repository_pk": str(acs_path.repository.pk),
                    "sync_policy": SYNC_POLICIES.MIRROR_CONTENT_ONLY,
                    "skip_types": skip_types,
                    "optimize": optimize,
                    "url": acs_url,
                },
            )

        # Update TaskGroup that all child task are dispatched
        task_group.finish()
        return TaskGroupOperationResponse(task_group, request)
