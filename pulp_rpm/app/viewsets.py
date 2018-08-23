from gettext import gettext as _  # noqa:F401

from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import detail_route

from pulpcore.plugin.models import RepositoryVersion
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositoryPublishURLSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.viewsets import (
    ContentViewSet,
    RemoteViewSet,
    OperationPostponedResponse,
    PublisherViewSet
)

from pulp_rpm.app import tasks
from pulp_rpm.app.models import RpmContent, RpmRemote, RpmPublisher
from pulp_rpm.app.serializers import (
    RpmContentSerializer,
    RpmRemoteSerializer,
    RpmPublisherSerializer
)


class RpmContentViewSet(ContentViewSet):
    """
    A ViewSet for RpmContent.

    Define endpoint name which will appear in the API endpoint for this content type.
    For example::
        http://pulp.example.com/pulp/api/v3/content/rpm/

    Also specify queryset and serializer for RpmContent.
    """

    endpoint_name = 'rpm'
    queryset = RpmContent.objects.all()
    serializer_class = RpmContentSerializer


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
