import logging
import os
import tempfile

import createrepo_c as cr
import rpmrepo_metadata as rpmmd
from django.db import transaction

from pulpcore.plugin.models import Content, CreatedResource, PulpTemporaryFile
from pulpcore.plugin.util import get_domain

from pulp_rpm.app.comps import comps_to_model_dicts
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
    created_objects = []
    all_objects = []
    curr_domain = get_domain()

    # Decompress and parse the comps XML file
    with comps_file.file.open("rb") as comps_uploaded:
        with tempfile.NamedTemporaryFile(dir=".", delete=False) as comps_on_disk:
            comps_on_disk.write(comps_uploaded.read())
            comps_on_disk.flush()
        with tempfile.TemporaryDirectory(dir=".") as tf:
            decompressed_path = os.path.join(tf, "comps.xml")
            cr.decompress_file(comps_on_disk.name, decompressed_path, cr.AUTO_DETECT_COMPRESSION)
            with open(decompressed_path) as f:
                comps = rpmmd.CompsData.from_xml(f.read())

    # Convert to model dicts with digests
    group_dicts, category_dicts, environment_dicts, langpack_dict = comps_to_model_dicts(
        comps, curr_domain
    )

    # Save langpacks to DB
    if langpack_dict is not None:
        langpack, created = PackageLangpacks.objects.get_or_create(**langpack_dict)
        if created:
            created_objects.append(langpack)
        all_objects.append(langpack)

    # Save categories to DB
    for category_dict in category_dicts:
        packagecategory, created = PackageCategory.objects.get_or_create(**category_dict)
        if created:
            created_objects.append(packagecategory)
        all_objects.append(packagecategory)

    # Save environments to DB
    for environment_dict in environment_dicts:
        packageenvironment, created = PackageEnvironment.objects.get_or_create(**environment_dict)
        if created:
            created_objects.append(packageenvironment)
        all_objects.append(packageenvironment)

    # Save groups to DB
    for group_dict in group_dicts:
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
