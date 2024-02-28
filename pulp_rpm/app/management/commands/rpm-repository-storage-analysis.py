import json
import re
import sys
from gettext import gettext as _

from argparse import RawDescriptionHelpFormatter
from django.core.management import BaseCommand
from django.conf import settings

from pulp_rpm.app.models import RpmRepository
from pulpcore.plugin.util import get_url, extract_pk


def gather_repository_sizes(
    repositories, include_on_demand=False, include_published_metadata=False
):
    """
    Creates a list containing the size report for given repositories.

    Each entry in the list will contain a dict with following minimal fields:
        - name: name of the repository
        - href: href of the repository
        - disk-size: size in bytes of all artifacts stored on disk in the repository

    Each entry can additionally have the optional fields if specified:
        - on-demand-size: approximate size in bytes of all on-demand artifacts in the repository
        - published-metadata-size: size in bytes of all published metadata for the repository

    **Note**: This does not account for the fact that the same artifact can appear in multiple
    repositories without incurring additional disk storage use. User interpretation of these numbers
    for individual repositories should consider totals across multiple repositories in the context
    that artifacts may be shared.
    """
    full_report = []
    for repo in repositories.order_by("name").iterator():
        report = {"name": repo.name, "href": get_url(repo), "disk-size": repo.disk_size}
        if include_on_demand:
            report["on-demand-size"] = repo.on_demand_size
        if include_published_metadata:
            report["published-metadata-size"] = repo.published_metadata_size
        full_report.append(report)

    return full_report


def href_list_handler(value):
    """Common list parsing for a string of hrefs."""
    r = rf"({settings.API_ROOT}(?:[-_a-zA-Z0-9]+/)?api/v3/repositories/[-_a-z]+/[-_a-z]+/[-a-f0-9]+/)"  # noqa: E501
    return re.findall(r, value)


class Command(BaseCommand):
    """Django management command for calculating the storage size of a repository."""

    help = __doc__ + gather_repository_sizes.__doc__

    def add_arguments(self, parser):
        """Set up arguments."""
        parser.add_argument(
            "--repositories",
            type=href_list_handler,
            required=False,
            help=_(
                "List of repository hrefs to generate the report from. Leave blank to include"
                " all repositories."
            ),
        )
        parser.add_argument(
            "--include-on-demand",
            action="store_true",
            help=_("Include the approximate on-demand artifact sizes"),
        )
        parser.add_argument(
            "--include-published-metadata",
            action="store_true",
            help=_("Include the size for the published metadata"),
        )

        parser.formatter_class = RawDescriptionHelpFormatter

    def handle(self, *args, **options):
        """Implement the command."""
        repository_hrefs = options.get("repositories")

        repositories = RpmRepository.objects.all()
        if repository_hrefs:
            repos_ids = [extract_pk(r) for r in repository_hrefs]
            repositories = repositories.filter(pk__in=repos_ids)

        report = gather_repository_sizes(
            repositories,
            include_on_demand=options["include_on_demand"],
            include_published_metadata=options["include_published_metadata"],
        )
        json.dump({"repositories": report}, sys.stdout, indent=4)
        print()
