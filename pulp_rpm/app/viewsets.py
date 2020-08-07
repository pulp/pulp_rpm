from django_filters import CharFilter
from gettext import gettext as _

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.serializers import ValidationError as DRFValidationError

from pulpcore.plugin.actions import ModifyRepositoryActionMixin
from pulpcore.plugin.models import RepositoryVersion, Content
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer
from pulpcore.plugin.viewsets import (
    BaseDistributionViewSet,
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
)

from pulp_rpm.app import tasks
from pulp_rpm.app.models import (
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
    RpmRepository,
    RpmPublication,
    UpdateRecord,
)
from pulp_rpm.app.serializers import (
    CopySerializer,
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
            'name': ['exact', 'in', 'ne'],
            'epoch': ['exact', 'in', 'ne'],
            'version': ['exact', 'in', 'ne'],
            'release': ['exact', 'in', 'ne'],
            'arch': ['exact', 'in', 'ne'],
            'pkgId': ['exact', 'in'],
            'checksum_type': ['exact', 'in', 'ne'],
        }


class PackageViewSet(SingleArtifactContentUploadViewSet):
    """
    A ViewSet for Package.

    Define endpoint name which will appear in the API endpoint for this content type.
    For example::
        http://pulp.example.com/pulp/api/v3/content/rpm/packages/

    Also specify queryset and serializer for Package.
    """

    endpoint_name = 'packages'
    queryset = Package.objects.prefetch_related("_artifacts")
    serializer_class = PackageSerializer
    minimal_serializer_class = MinimalPackageSerializer
    filterset_class = PackageFilter


class RpmRepositoryViewSet(RepositoryViewSet, ModifyRepositoryActionMixin):
    """
    A ViewSet for RpmRepository.
    """

    endpoint_name = 'rpm'
    queryset = RpmRepository.objects.exclude(sub_repo=True)
    serializer_class = RpmRepositorySerializer

    @extend_schema(
        description="Trigger an asynchronous task to sync RPM content.",
        summary="Sync from remote",
        responses={202: AsyncOperationResponseSerializer}
    )
    @action(detail=True, methods=['post'], serializer_class=RpmRepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Dispatches a sync task.
        """
        repository = self.get_object()
        serializer = RpmRepositorySyncURLSerializer(
            data=request.data,
            context={'request': request, 'repository_pk': pk}
        )
        serializer.is_valid(raise_exception=True)
        remote = serializer.validated_data.get('remote', repository.remote)
        mirror = serializer.validated_data.get('mirror')
        skip_types = serializer.validated_data.get('skip_types')
        optimize = serializer.validated_data.get('optimize')

        if repository.retain_package_versions > 0 and mirror:
            raise DRFValidationError("Cannot use 'retain_package_versions' with mirror-mode sync")

        result = enqueue_with_reservation(
            tasks.synchronize,
            [repository, remote],
            kwargs={
                'mirror': mirror,
                'remote_pk': remote.pk,
                'repository_pk': repository.pk,
                'skip_types': skip_types,
                'optimize': optimize
            }
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

    endpoint_name = 'rpm'
    queryset = RpmRemote.objects.all()
    serializer_class = RpmRemoteSerializer


class UpdateRecordFilter(ContentFilter):
    """
    FilterSet for UpdateRecord.
    """

    class Meta:
        model = UpdateRecord
        fields = {
            'id': ['exact', 'in'],
            'status': ['exact', 'in', 'ne'],
            'severity': ['exact', 'in', 'ne'],
            'type': ['exact', 'in', 'ne'],
        }


class UpdateRecordViewSet(NoArtifactContentUploadViewSet):
    """
    A ViewSet for UpdateRecord.

    Define endpoint name which will appear in the API endpoint for this content type.
    For example::
        http://pulp.example.com/pulp/api/v3/content/rpm/advisories/

    Also specify queryset and serializer for UpdateRecord.
    """

    endpoint_name = 'advisories'
    queryset = UpdateRecord.objects.all()
    serializer_class = UpdateRecordSerializer
    minimal_serializer_class = MinimalUpdateRecordSerializer
    filterset_class = UpdateRecordFilter


class RpmPublicationViewSet(PublicationViewSet):
    """
    ViewSet for Rpm Publications.
    """

    endpoint_name = 'rpm'
    queryset = RpmPublication.objects.exclude(complete=False)
    serializer_class = RpmPublicationSerializer

    @extend_schema(
        description="Trigger an asynchronous task to create a new RPM "
                    "content publication.",
        responses={202: AsyncOperationResponseSerializer}
    )
    def create(self, request):
        """
        Dispatches a publish task.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repository_version = serializer.validated_data.get('repository_version')
        repository = RpmRepository.objects.get(pk=repository_version.repository.pk)
        metadata_checksum_type = serializer.validated_data.get('metadata_checksum_type', "")
        package_checksum_type = serializer.validated_data.get('package_checksum_type', "")
        checksum_types = dict(
            metadata=metadata_checksum_type,
            package=package_checksum_type,
        )

        result = enqueue_with_reservation(
            tasks.publish,
            [repository_version.repository],
            kwargs={
                'repository_version_pk': repository_version.pk,
                'metadata_signing_service': repository.metadata_signing_service,
                'checksum_types': checksum_types,
            }
        )
        return OperationPostponedResponse(result, request)


class RpmDistributionViewSet(BaseDistributionViewSet):
    """
    ViewSet for RPM Distributions.
    """

    endpoint_name = 'rpm'
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
        responses={202: AsyncOperationResponseSerializer}
    )
    def create(self, request):
        """Copy content."""
        serializer = CopySerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        dependency_solving = serializer.validated_data['dependency_solving']
        config = serializer.validated_data['config']

        config, repos = self._process_config(config)

        async_result = enqueue_with_reservation(
            tasks.copy_content, repos,
            args=[config, dependency_solving],
            kwargs={}
        )
        return OperationPostponedResponse(async_result, request)

    def _process_config(self, config):
        """
        Change the hrefs into pks within config.

        This method also implicitly validates that the hrefs map to objects and it returns a list of
        repos so that the task can lock on them.
        """
        result = []
        repos = []

        for entry in config:
            r = dict()
            source_version = NamedModelViewSet().get_resource(entry["source_repo_version"],
                                                              RepositoryVersion)
            dest_repo = NamedModelViewSet().get_resource(entry["dest_repo"], RpmRepository)
            r["source_repo_version"] = source_version.pk
            r["dest_repo"] = dest_repo.pk
            repos.extend((source_version.repository, dest_repo))

            if "dest_base_version" in entry:
                try:
                    r["dest_base_version"] = dest_repo.versions.\
                        get(number=entry["dest_base_version"]).pk
                except RepositoryVersion.DoesNotExist:
                    message = _("Version {version} does not exist for repository "
                                "'{repo}'.").format(version=entry["dest_base_version"],
                                                    repo=dest_repo.name)
                    raise DRFValidationError(detail=message)

            if entry.get("content") is not None:
                r["content"] = []
                for c in entry["content"]:
                    r["content"].append(NamedModelViewSet().get_resource(c, Content).pk)
            result.append(r)

        return result, repos


class PackageGroupViewSet(ReadOnlyContentViewSet,
                          mixins.DestroyModelMixin):
    """
    PackageGroup ViewSet.
    """

    endpoint_name = 'packagegroups'
    queryset = PackageGroup.objects.all()
    serializer_class = PackageGroupSerializer


class PackageCategoryViewSet(ReadOnlyContentViewSet,
                             mixins.DestroyModelMixin):
    """
    PackageCategory ViewSet.
    """

    endpoint_name = 'packagecategories'
    queryset = PackageCategory.objects.all()
    serializer_class = PackageCategorySerializer


class PackageEnvironmentViewSet(ReadOnlyContentViewSet,
                                mixins.DestroyModelMixin):
    """
    PackageEnvironment ViewSet.
    """

    endpoint_name = 'packageenvironments'
    queryset = PackageEnvironment.objects.all()
    serializer_class = PackageEnvironmentSerializer


class PackageLangpacksViewSet(ReadOnlyContentViewSet,
                              mixins.DestroyModelMixin):
    """
    PackageLangpacks ViewSet.
    """

    endpoint_name = 'packagelangpacks'
    queryset = PackageLangpacks.objects.all()
    serializer_class = PackageLangpacksSerializer


class DistributionTreeViewSet(ReadOnlyContentViewSet,
                              mixins.DestroyModelMixin):
    """
    Distribution Tree Viewset.

    """

    endpoint_name = 'distribution_trees'
    queryset = DistributionTree.objects.all()
    serializer_class = DistributionTreeSerializer


class RepoMetadataFileViewSet(ReadOnlyContentViewSet,
                              mixins.DestroyModelMixin):
    """
    RepoMetadataFile Viewset.

    """

    endpoint_name = 'repo_metadata_files'
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
            'name': ['exact', 'in'],
            'stream': ['exact', 'in'],
        }


class ModulemdViewSet(SingleArtifactContentUploadViewSet):
    """
    ViewSet for Modulemd.
    """

    endpoint_name = 'modulemds'
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
            'module': ['exact', 'in'],
            'stream': ['exact', 'in'],
        }


class ModulemdDefaultsViewSet(SingleArtifactContentUploadViewSet):
    """
    ViewSet for Modulemd.
    """

    endpoint_name = 'modulemd_defaults'
    queryset = ModulemdDefaults.objects.all()
    serializer_class = ModulemdDefaultsSerializer
    filterset_class = ModulemdDefaultsFilter
