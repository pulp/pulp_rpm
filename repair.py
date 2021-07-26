import asyncio
import logging
import shutil
import sys
import tempfile

import createrepo_c as cr

import django
django.setup()

from django.core.files.storage import default_storage as storage

from pulpcore.plugin.models import (
    ContentArtifact,
    RepositoryVersion,
)
from pulpcore.tasking.util import get_url
from pulp_rpm.app.models import (
    Package,
    RpmPublication,
    RpmRemote,
    RpmRepository,
    RpmDistribution,
)

log = logging.getLogger(__name__)
loop = asyncio.get_event_loop()

broken_criteria = {
    "files": [],
    "changelogs": [],
}
broken_packages = Package.objects.filter(**broken_criteria)
broken_package_ids = list(broken_packages.values_list("pk", flat=True))

print("""
##########################################
#  Repair tool for Pulp RPM issue #9107  #
#    https://pulp.plan.io/issues/9107    #
##########################################""")

print(
"""
Analysis
========
"""
)

total_packages = Package.objects.all().count()
total_broken_packages = broken_packages.count()
print("Total packages with broken metadata: {}/{}".format(total_broken_packages, total_packages))

broken_content_artifacts = ContentArtifact.objects.filter(content__in=broken_packages)
assert broken_content_artifacts.count() == total_broken_packages

broken_content_artifacts_with_files = broken_content_artifacts.filter(artifact__isnull=False)
broken_content_artifacts_without_files = broken_content_artifacts.filter(artifact__isnull=True)

total_broken_packages_with_artifacts = broken_content_artifacts_with_files.count()
print("Total packages with broken metadata, with local RPMs available: {}/{}".format(total_broken_packages_with_artifacts, total_broken_packages))

total_broken_packages_download_needed = total_broken_packages - total_broken_packages_with_artifacts
print("Total packages with broken metadata, without local RPMs available: {}/{}".format(total_broken_packages_download_needed, total_broken_packages))

print(
"""
Repair
======
"""
)

total_packages_repaired = 0


def update_total():
    global total_packages_repaired
    global total_broken_packages
    sys.stdout.write("\rPackage metadata repaired: {}/{}".format(total_packages_repaired, total_broken_packages))
    sys.stdout.flush()

# Repair on-disk Packages
# =======================


packages_to_update = []
for ca in broken_content_artifacts_with_files.select_related("artifact", "content").iterator():
    with storage.open(ca.artifact.file.name) as fp:
        with tempfile.NamedTemporaryFile("wb", suffix="blah.rpm") as temp_file:
            shutil.copyfileobj(fp, temp_file)
            temp_file.flush()
            cr_pkginfo = cr.package_from_rpm(temp_file.name)

        new_package = Package.createrepo_to_dict(cr_pkginfo)
        old_package = ca.content.rpm_package  # not very efficient, but for a one-time script it's "fine".

        old_package.files = new_package["files"]
        old_package.changelogs = new_package["changelogs"]

        packages_to_update.append(old_package)

    if len(packages_to_update) >= 50:
        Package.objects.bulk_update(packages_to_update, fields=["files", "changelogs"])
        total_packages_repaired += len(packages_to_update)
        packages_to_update.clear()
        update_total()
        # not worth cleaning up the duplicated code
else:
    Package.objects.bulk_update(packages_to_update, fields=["files", "changelogs"])
    total_packages_repaired += len(packages_to_update)
    packages_to_update.clear()
    update_total()

# Repair on-demand Packages
# =========================


async def repair_on_demand_content(content, remote_artifacts):
    import aiofiles
    import aiofiles.os
    import createrepo_c as cr
    from pulp_rpm.app.models import Package

    async with aiofiles.tempfile.TemporaryDirectory():
        for remote_artifact in remote_artifacts:
            remote = remote_artifact.remote
            downloader = remote.get_downloader(remote_artifact=remote_artifact)
            download_result = await downloader.run()

            cr_pkginfo = cr.package_from_rpm(download_result.path)
            new_package = Package.createrepo_to_dict(cr_pkginfo)
            old_package = content.rpm_package  # not very efficient, but for a one-time script it's "fine".
            await aiofiles.os.remove(download_result.path)

            old_package.files = new_package["files"]
            old_package.changelogs = new_package["changelogs"]

            return old_package

packages_to_update = []

for ca in broken_content_artifacts_without_files.select_related("content").iterator():
    remote_artifacts = list(ca.remoteartifact_set.all().select_related("remote"))
    package = repair_on_demand_content(ca.content, remote_artifacts)
    packages_to_update.append(package)
    if len(packages_to_update) >= 10:
        packages_to_update = loop.run_until_complete(asyncio.gather(*packages_to_update))
        Package.objects.bulk_update(packages_to_update, fields=["files", "changelogs"])
        total_packages_repaired += len(packages_to_update)
        packages_to_update.clear()
        update_total()
        # not worth cleaning up the duplicated code
else:
    packages_to_update = loop.run_until_complete(asyncio.gather(*packages_to_update))
    Package.objects.bulk_update(packages_to_update, fields=["files", "changelogs"])
    total_packages_repaired += len(packages_to_update)
    packages_to_update.clear()
    update_total()

print(" ...FINISHED\n")

# import pydevd_pycharm
# pydevd_pycharm.settrace('localhost', port=12735, stdoutToServer=True, stderrToServer=True)

if not total_packages_repaired:
    print("No further actions required.")
else:
    repo_versions = RepositoryVersion.objects.filter(
        publication__in=RpmPublication.objects.filter(
            complete=True,
            repository_version__in=RepositoryVersion.objects.with_content(
                Package.objects.filter(pk__in=broken_package_ids)
            )
        )
    )

    repo_versions = list(repo_versions)

    if not repo_versions:
        print("No further actions required.")
    else:
        print("Please save the following information for reference, as it cannot be reproduced.")

        print("The following publications (potentially) contain incorrect metadata:\n")

        for version in repo_versions:
            for publication in RpmPublication.objects.filter(repository_version=version, complete=True).iterator():
                print("\t {}".format(get_url(publication)))

                print(
                    (
                        "\t\t Created from repository '{name}' version {v}\n"
                        "\t\t\t /pulp/api/v3/repositories/rpm/rpm/{pk}/versions/{v}/\n"
                    ).format(name=version.repository.name, pk=str(version.repository.pk), v=version.number)
                )

                distributions = list(RpmDistribution.objects.filter(publication=publication))
                if distributions:
                    print("\t\t Currently being (directly) distributed by:")
                    for distribution in distributions:
                        print("\t\t\t {}".format(get_url(distribution)))


        #     "Please save the following information for reference, as it cannot be recreated.\n\n"
        #     "The following is a list of publications (published metadata) which may\n"
        #     "potentially contain incorrect metadata. In many cases, this is not a cause for\n"
        #     "concern, since updates to repositories are likely to replace the bad metadata\n"
        #     "in due course. However, depending on your urgency and requirements, it may be\n"
        #     "prudent to manually update them to ensure correct metadata is available.\n"
        #     "Information about all potentially-impacted repositories is therefore available\n"
        #     "below. Our recommendation to the most cautious of users is to delete all impacted\n"
        #     "'publications' using the pulp CLI and, for the ones which are currently being\n"
        #     "distributed via some 'distribution', to re-create publications for these repos.\n"
        # )
