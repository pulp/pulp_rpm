from gettext import gettext as _

from django.db import transaction
from django.db.utils import IntegrityError
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers, status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import FormParser, MultiPartParser

from pulpcore.plugin.models import Artifact
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositorySyncURLSerializer
)
from pulpcore.plugin.viewsets import (
    BaseDistributionViewSet,
    ContentFilter,
    ContentViewSet,
    RemoteViewSet,
    NamedModelViewSet,
    OperationPostponedResponse,
    PublicationViewSet
)

from pulp_rpm.app import tasks
from pulp_rpm.app.shared_utils import _prepare_package
from pulp_rpm.app.models import (
    DistributionTree,
    Package,
    RpmDistribution,
    RpmRemote,
    RpmPublication,
    UpdateRecord
)

from pulp_rpm.app.serializers import (
    CopySerializer,
    DistributionTreeSerializer,
    MinimalPackageSerializer,
    MinimalUpdateRecordSerializer,
    OneShotUploadSerializer,
    PackageSerializer,
    RpmDistributionSerializer,
    RpmRemoteSerializer,
    RpmPublicationSerializer,
    UpdateRecordSerializer,
)


class PackageFilter(ContentFilter):
    """
    FilterSet for Package.
    """

    class Meta:
        model = Package
        fields = {
            'name': ['exact', 'in'],
            'epoch': ['exact', 'in'],
            'version': ['exact', 'in'],
            'release': ['exact', 'in'],
            'arch': ['exact', 'in'],
            'pkgId': ['exact', 'in'],
            'checksum_type': ['exact', 'in'],
        }


class PackageViewSet(ContentViewSet):
    """
    A ViewSet for Package.

    Define endpoint name which will appear in the API endpoint for this content type.
    For example::
        http://pulp.example.com/pulp/api/v3/content/rpm/packages/

    Also specify queryset and serializer for Package.
    """

    endpoint_name = 'packages'
    queryset = Package.objects.all()
    serializer_class = PackageSerializer
    minimal_serializer_class = MinimalPackageSerializer
    filterset_class = PackageFilter

    @transaction.atomic
    def create(self, request):
        """
        Create a new Package from a request.
        """
        try:
            artifact = self.get_resource(request.data['_artifact'], Artifact)
        except KeyError:
            raise serializers.ValidationError(detail={'_artifact': _('This field is required')})

        try:
            relative_path = request.data['relative_path']
        except KeyError:
            raise serializers.ValidationError(detail={'relative_path': _('This field is required')})

        try:
            new_pkg = _prepare_package(artifact, relative_path)
            new_pkg['_artifact'] = request.data['_artifact']
            new_pkg['relative_path'] = relative_path
        except OSError:
            return Response('RPM file cannot be parsed for metadata.',
                            status=status.HTTP_406_NOT_ACCEPTABLE)

        serializer = self.get_serializer(data=new_pkg)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        headers = self.get_success_headers(request.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class RpmRemoteViewSet(RemoteViewSet):
    """
    A ViewSet for RpmRemote.
    """

    endpoint_name = 'rpm'
    queryset = RpmRemote.objects.all()
    serializer_class = RpmRemoteSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to sync RPM content.",
        operation_summary="Sync from remote",
        responses={202: AsyncOperationResponseSerializer}
    )
    @action(detail=True, methods=['post'], serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Dispatches a sync task.
        """
        remote = self.get_object()
        serializer = RepositorySyncURLSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data.get('repository')

        result = enqueue_with_reservation(
            tasks.synchronize,
            [repository, remote],
            kwargs={
                'remote_pk': remote.pk,
                'repository_pk': repository.pk
            }
        )
        return OperationPostponedResponse(result, request)


class UpdateRecordFilter(ContentFilter):
    """
    FilterSet for UpdateRecord.
    """

    class Meta:
        model = UpdateRecord
        fields = {
            'id': ['exact', 'in'],
            'status': ['exact', 'in'],
            'severity': ['exact', 'in'],
            'type': ['exact', 'in'],
        }


class UpdateRecordViewSet(ContentViewSet):
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


class OneShotUploadViewSet(viewsets.ViewSet):
    """
    ViewSet for One Shot RPM Upload.

    Args:
        file@: package to upload
    Optional:
        repository: repository to update
    """

    serializer_class = OneShotUploadSerializer
    parser_classes = (MultiPartParser, FormParser)

    @swagger_auto_schema(
        operation_description="Create an artifact and trigger an asynchronous"
                              "task to create RPM content from it, optionally"
                              "create new repository version.",
        operation_summary="Upload a package",
        operation_id="upload_rpm_package",
        request_body=OneShotUploadSerializer,
        responses={202: AsyncOperationResponseSerializer}
    )
    def create(self, request):
        """Upload an RPM package."""
        artifact = Artifact.init_and_validate(request.data['file'])
        filename = request.data['file'].name

        if 'repository' in request.data:
            serializer = OneShotUploadSerializer(
                data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            repository = serializer.validated_data['repository']
            repository_pk = repository.pk
        else:
            repository_pk = None

        try:
            artifact.save()
        except IntegrityError:
            # if artifact already exists, let's use it
            artifact = Artifact.objects.get(sha256=artifact.sha256)

        async_result = enqueue_with_reservation(
            tasks.one_shot_upload, [artifact],
            kwargs={
                'artifact_pk': artifact.pk,
                'filename': filename,
                'repository_pk': repository_pk,
            })
        return OperationPostponedResponse(async_result, request)


class RpmPublicationViewSet(PublicationViewSet):
    """
    ViewSet for Rpm Publications.
    """

    endpoint_name = 'rpm'
    queryset = RpmPublication.objects.all()
    serializer_class = RpmPublicationSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to create a new RPM "
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

        result = enqueue_with_reservation(
            tasks.publish,
            [repository_version.repository],
            kwargs={
                'repository_version_pk': repository_version.pk
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
    parser_classes = (MultiPartParser, FormParser)

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to copy RPM content"
                              "from one repository into another, creating a new"
                              "repository version.",
        operation_summary="Copy content",
        operation_id="copy_content",
        request_body=CopySerializer,
        responses={202: AsyncOperationResponseSerializer}
    )
    def create(self, request):
        """Copy content."""
        serializer = CopySerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        source_repo = serializer.validated_data['source_repo']
        source_repo_version = serializer.validated_data['source_repo_version']
        dest_repo = serializer.validated_data['dest_repo']
        types = serializer.validated_data['types']

        async_result = enqueue_with_reservation(
            tasks.copy_content, [source_repo, dest_repo],
            args=[source_repo_version.pk, dest_repo.pk, types],
            kwargs={}
        )
        return OperationPostponedResponse(async_result, request)


class DistributionTreeViewSet(NamedModelViewSet,
                              mixins.RetrieveModelMixin,
                              mixins.ListModelMixin,
                              mixins.DestroyModelMixin):
    """
    Distribution Tree Viewset.

    """

    endpoint_name = 'distribution_trees'
    queryset = DistributionTree.objects.all()
    serializer_class = DistributionTreeSerializer
