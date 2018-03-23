from gettext import gettext as _

from rest_framework.decorators import detail_route
from rest_framework import serializers

from pulpcore.plugin.models import Repository, RepositoryVersion

from pulpcore.plugin.viewsets import (
    ContentViewSet,
    ImporterViewSet,
    OperationPostponedResponse,
    PublisherViewSet)

from . import tasks
from .models import RpmContent, RpmImporter, RpmPublisher
from .serializers import RpmContentSerializer, RpmImporterSerializer, RpmPublisherSerializer


class RpmContentViewSet(ContentViewSet):
    """
    A ViewSet for RpmContent.

    Define endpoint name which will appear in the API endpoint for this content type.
    For example::
        http://pulp.example.com/api/v3/content/rpm/

    Also specify queryset and serializer for RpmContent.
    """
    endpoint_name = 'rpm'
    queryset = RpmContent.objects.all()
    serializer_class = RpmContentSerializer


class RpmImporterViewSet(ImporterViewSet):
    """
    A ViewSet for RpmImporter.
    """
    endpoint_name = 'rpm'
    queryset = RpmImporter.objects.all()
    serializer_class = RpmImporterSerializer

    @detail_route(methods=('post',))
    def sync(self, request, pk):
        importer = self.get_object()
        try:
            repository_uri = request.data['repository']
        except KeyError:
            raise serializers.ValidationError(detail=_('Repository URI must be specified.'))
        repository = self.get_resource(repository_uri, Repository)
        if not importer.feed_url:
            raise serializers.ValidationError(detail=_('A feed_url must be specified.'))
        result = tasks.synchronize.apply_async_with_reservation(
            [repository, importer],
            kwargs={
                'importer_pk': importer.pk,
                'repository_pk': repository.pk
            }
        )
        return OperationPostponedResponse([result], request)


class RpmPublisherViewSet(PublisherViewSet):
    """
    A ViewSet for RpmPublisher.
    """
    endpoint_name = 'rpm'
    queryset = RpmPublisher.objects.all()
    serializer_class = RpmPublisherSerializer

    @detail_route(methods=('post',))
    def publish(self, request, pk):
        publisher = self.get_object()
        repository = None
        repository_version = None
        if 'repository' not in request.data and 'repository_version' not in request.data:
            raise serializers.ValidationError(_("Either the 'repository' or 'repository_version' "
                                              "need to be specified."))

        if 'repository' in request.data and request.data['repository']:
            repository = self.get_resource(request.data['repository'], Repository)

        if 'repository_version' in request.data and request.data['repository_version']:
            repository_version = self.get_resource(request.data['repository_version'],
                                                   RepositoryVersion)

        if repository and repository_version:
            raise serializers.ValidationError(_("Either the 'repository' or 'repository_version' "
                                              "can be specified - not both."))

        if not repository_version:
            repository_version = RepositoryVersion.latest(repository)

        result = tasks.publish.apply_async_with_reservation(
            [repository_version.repository, publisher],
            kwargs={
                'publisher_pk': str(publisher.pk),
                'repository_version_pk': str(repository_version.pk)
            }
        )
        return OperationPostponedResponse([result], request)
