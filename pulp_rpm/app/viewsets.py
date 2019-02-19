from gettext import gettext as _

from django.db import transaction
from django.db.utils import IntegrityError
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers, status, views
from rest_framework.decorators import detail_route
from rest_framework.response import Response

from pulpcore.plugin.models import Artifact, ContentArtifact, RepositoryVersion
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositoryPublishURLSerializer,
    RepositorySyncURLSerializer
)
from pulpcore.plugin.viewsets import (
    ContentFilter,
    ContentViewSet,
    RemoteViewSet,
    OperationPostponedResponse,
    PublisherViewSet
)

from pulp_rpm.app import tasks
from pulp_rpm.app.shared_utils import _prepare_package
from pulp_rpm.app.models import Package, RpmRemote, RpmPublisher, UpdateRecord
from pulp_rpm.app.serializers import (
    MinimalPackageSerializer,
    PackageSerializer,
    RpmRemoteSerializer,
    RpmPublisherSerializer,
    UpdateRecordSerializer,
    MinimalUpdateRecordSerializer,
    OneShotUploadSerializer,
)

from .upload import one_shot_upload


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
            filename = request.data['filename']
        except KeyError:
            raise serializers.ValidationError(detail={'filename': _('This field is required')})

        try:
            new_pkg = _prepare_package(artifact, filename)
            new_pkg['_artifact'] = request.data['_artifact']
        except OSError:
            return Response('RPM file cannot be parsed for metadata.')

        serializer = self.get_serializer(data=new_pkg)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop('_artifact')
        package = serializer.save()
        if package.pk:
            ContentArtifact.objects.create(
                artifact=artifact,
                content=package,
                relative_path=package.filename
            )

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
        responses={202: AsyncOperationResponseSerializer}
    )
    @detail_route(methods=('post',), serializer_class=RepositorySyncURLSerializer)
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


class RpmPublisherViewSet(PublisherViewSet):
    """
    A ViewSet for RpmPublisher.
    """

    endpoint_name = 'rpm'
    queryset = RpmPublisher.objects.all()
    serializer_class = RpmPublisherSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to publish RPM content.",
        responses={202: AsyncOperationResponseSerializer}
    )
    @detail_route(methods=('post',), serializer_class=RepositoryPublishURLSerializer)
    def publish(self, request, pk):
        """
        Dispatches a publish task.
        """
        publisher = self.get_object()
        serializer = RepositoryPublishURLSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        repository_version = serializer.validated_data.get('repository_version')

        # Safe because version OR repository is enforced by serializer.
        if not repository_version:
            repository = serializer.validated_data.get('repository')
            repository_version = RepositoryVersion.latest(repository)

        result = enqueue_with_reservation(
            tasks.publish,
            [repository_version.repository, publisher],
            kwargs={
                'publisher_pk': publisher.pk,
                'repository_version_pk': repository_version.pk
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
        http://pulp.example.com/pulp/api/v3/content/rpm/errata/

    Also specify queryset and serializer for UpdateRecord.
    """

    endpoint_name = 'errata'
    queryset = UpdateRecord.objects.all()
    serializer_class = UpdateRecordSerializer
    minimal_serializer_class = MinimalUpdateRecordSerializer
    filterset_class = UpdateRecordFilter


class OneShotUploadView(views.APIView):
    """
    ViewSet for One Shot RPM Upload.

    Args:
        file@: package to upload
    Optional:
        repository: repository to update
    """

    def post(self, request):
        """Upload an RPM package."""
        serializer = OneShotUploadSerializer(
            data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        artifact = Artifact.init_and_validate(request.data['file'])

        if 'repository' in request.data:
            repository = serializer.validated_data['repository']
        else:
            repository = None

        try:
            artifact.save()
        except IntegrityError:
            # if artifact already exists, let's use it
            artifact = Artifact.objects.get(sha256=artifact.sha256)

        async_result = enqueue_with_reservation(
            one_shot_upload, [artifact],
            kwargs={
                'artifact': artifact,
                'repository': repository,
            })
        return OperationPostponedResponse(async_result, request)
