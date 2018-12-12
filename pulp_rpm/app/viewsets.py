from gettext import gettext as _
import json
import os
import shutil
import tempfile

import createrepo_c
from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers, status
from rest_framework.decorators import detail_route
from rest_framework.response import Response

from pulpcore.plugin.models import Artifact, RepositoryVersion
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositoryPublishURLSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.viewsets import (
    ContentFilter,
    ContentViewSet,
    RemoteViewSet,
    OperationPostponedResponse,
    PublisherViewSet
)

from pulp_rpm.app import tasks
from pulp_rpm.app.models import Package, RpmRemote, RpmPublisher, UpdateRecord
from pulp_rpm.app.serializers import (
    MinimalPackageSerializer,
    PackageSerializer,
    RpmRemoteSerializer,
    RpmPublisherSerializer,
    UpdateRecordSerializer,
    MinimalUpdateRecordSerializer
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

    endpoint_name = 'rpm/packages'
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
            artifact = self.get_resource(request.data['artifact'], Artifact)
        except KeyError:
            raise serializers.ValidationError(detail={'artifact': _('This field is required')})

        try:
            filename = request.data['filename']
        except KeyError:
            raise serializers.ValidationError(detail={'filename': _('This field is required')})

        # Copy file to a temp directory under the user provided filename
        with tempfile.TemporaryDirectory() as td:
            temp_path = os.path.join(td, filename)
            shutil.copy2(artifact.file.path, temp_path)
            cr_pkginfo = createrepo_c.package_from_rpm(temp_path)
            package = Package.createrepo_to_dict(cr_pkginfo)

        package['location_href'] = filename
        package['artifact'] = request.data['artifact']

        # TODO: Clean this up, maybe make a new function for the purpose of parsing it into
        # a saveable format
        new_pkg = {}
        for key, value in package.items():
            if isinstance(value, list):
                new_pkg[key] = json.dumps(value)
            else:
                new_pkg[key] = value

        serializer = self.get_serializer(data=new_pkg)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

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
            'errata_id': ['exact', 'in'],
            'status': ['exact', 'in'],
            'severity': ['exact', 'in'],
            'update_type': ['exact', 'in'],
        }


class UpdateRecordViewSet(ContentViewSet):
    """
    A ViewSet for UpdateRecord.

    Define endpoint name which will appear in the API endpoint for this content type.
    For example::
        http://pulp.example.com/pulp/api/v3/content/rpm/errata/

    Also specify queryset and serializer for UpdateRecord.
    """

    endpoint_name = 'rpm/errata'
    queryset = UpdateRecord.objects.all()
    serializer_class = UpdateRecordSerializer
    minimal_serializer_class = MinimalUpdateRecordSerializer
    filterset_class = UpdateRecordFilter
