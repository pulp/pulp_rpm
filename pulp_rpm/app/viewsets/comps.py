from drf_spectacular.utils import extend_schema
from rest_framework import viewsets

from pulpcore.plugin.models import PulpTemporaryFile
from pulpcore.plugin.tasking import dispatch
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
)
from pulpcore.plugin.viewsets import (
    OperationPostponedResponse,
    ReadOnlyContentViewSet,
)

from pulp_rpm.app import tasks
from pulp_rpm.app.models import (
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    PackageLangpacks,
)
from pulp_rpm.app.serializers import (
    CompsXmlSerializer,
    PackageCategorySerializer,
    PackageEnvironmentSerializer,
    PackageGroupSerializer,
    PackageLangpacksSerializer,
)


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
