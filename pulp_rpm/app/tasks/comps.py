import libcomps
import logging

from django.db import transaction

from pulpcore.plugin.models import PulpTemporaryFile, CreatedResource
from pulpcore.plugin.models import Content
from pulp_rpm.app.comps import strdict_to_dict, dict_digest

from pulp_rpm.app.models import (
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    PackageLangpacks,
    RpmRepository,
)

log = logging.getLogger(__name__)


def parse_comps_components(comps_file):
    """Parse comps-related components found in the specified file."""
    # created = {"categories": [], "environments": [], "groups": [], "langpack": None}
    created_objects = []
    all_objects = []
    comps = libcomps.Comps()
    # Read the file and pass the string along because comps.fromxml_f() will only take a
    # path-string that doesn't work on things like S3 storage
    with comps_file.file.open("rb") as f:
        data = f.read()
        comps.fromxml_str(data.decode("utf-8"))

    if comps.langpacks:
        langpack_dict = PackageLangpacks.libcomps_to_dict(comps.langpacks)
        langpack, created = PackageLangpacks.objects.get_or_create(
            matches=strdict_to_dict(comps.langpacks), digest=dict_digest(langpack_dict)
        )
        if created:
            created_objects.append(langpack)
        all_objects.append(langpack)

    if comps.categories:
        for category in comps.categories:
            category_dict = PackageCategory.libcomps_to_dict(category)
            category_dict["digest"] = dict_digest(category_dict)
            packagecategory, created = PackageCategory.objects.get_or_create(**category_dict)
            if created:
                created_objects.append(packagecategory)
            all_objects.append(packagecategory)

    if comps.environments:
        for environment in comps.environments:
            environment_dict = PackageEnvironment.libcomps_to_dict(environment)
            environment_dict["digest"] = dict_digest(environment_dict)
            packageenvironment, created = PackageEnvironment.objects.get_or_create(
                **environment_dict
            )
            if created:
                created_objects.append(packageenvironment)
            all_objects.append(packageenvironment)

    if comps.groups:
        for group in comps.groups:
            group_dict = PackageGroup.libcomps_to_dict(group)
            group_dict["digest"] = dict_digest(group_dict)
            packagegroup, created = PackageGroup.objects.get_or_create(**group_dict)
            if created:
                created_objects.append(packagegroup)
            all_objects.append(packagegroup)

    return created_objects, all_objects


@transaction.atomic
def upload_comps(tmp_file_id, repo_id=None, replace=False):
    """
    Upload comps.xml file.

    Args:
        tmp_file_id: uploaded comps.xml file.
        repo_id: repository primary key to associate incoming comps-content to.
        replace: if true, replace existing comps-related Content in the specified
            repository with those in the incoming comps.xml file.
    """
    temp_file = PulpTemporaryFile.objects.get(pk=tmp_file_id)
    created, all_objs = parse_comps_components(temp_file)

    for content in all_objs:
        crsrc = CreatedResource(content_object=content)
        crsrc.save()

    if repo_id:
        repository = RpmRepository.objects.get(pk=repo_id)
        if repository:
            all_ids = [obj.content_ptr_id for obj in all_objs]
            with repository.new_version() as new_version:
                if replace:
                    latest = repository.latest_version()
                    rmv_ids = latest.content.filter(
                        pulp_type__in=(
                            PackageCategory.get_pulp_type(),
                            PackageEnvironment.get_pulp_type(),
                            PackageGroup.get_pulp_type(),
                            PackageLangpacks.get_pulp_type(),
                        )
                    )
                    new_version.remove_content(Content.objects.filter(pk__in=rmv_ids))
                new_version.add_content(Content.objects.filter(pk__in=all_ids))
