from gettext import gettext as _
import sys

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from pulp_rpm.app.models import Package  # noqa


class Command(BaseCommand):
    """
    Django management command for trimming changelog entries on packages in the Pulp database.

    RPM repositories contain a list of changelog entries for each package so that commands such
    as "dnf changelog" or "dnf repoquery --changelogs" can display it. Since this metadata can
    grow to be extremely large, typically you want to keep only a few changelogs for each package
    (if the package is actually installed on your system, you can view all changelogs with
    "rpm -qa $package --changelogs").

    In pulp_rpm 3.17 a new setting was introduced to enact this changelog limit, but it is not
    retroactively applied to packages that are already synced. This command will do so and can
    save a significant amount of disk space if Pulp is being used to sync RPM content from RHEL
    or Oracle Linux.
    """

    help = _(__doc__)

    def add_arguments(self, parser):
        """Set up arguments."""
        parser.add_argument(
            "--changelog-limit",
            default=settings.KEEP_CHANGELOG_LIMIT,
            type=int,
            required=False,
            help=_(
                "The number of changelogs you wish to keep for each package - the suggested "
                "value is 10. If this value is not provided the default configured as per the "
                "settings will be used."
            ),
        )

    def handle(self, *args, **options):
        """Implement the command."""
        changelog_limit = options["changelog_limit"]
        if changelog_limit <= 0:
            raise CommandError("--changelog-limit must be a non-zero positive integer")
        trimmed_packages = 0
        batch = []

        def update_total(total):
            sys.stdout.write("\rTrimmed changelogs for {} packages".format(total))
            sys.stdout.flush()

        for package in Package.objects.all().only("changelogs").iterator():
            # make sure the changelogs are ascending sorted by date
            package.changelogs.sort(key=lambda t: t[1])
            # take the last N changelogs
            package.changelogs = package.changelogs[-changelog_limit:]
            batch.append(package)
            if len(batch) > 500:
                Package.objects.bulk_update(batch, fields=["changelogs"])
                trimmed_packages += len(batch)
                batch.clear()
                update_total(trimmed_packages)

        Package.objects.bulk_update(batch, fields=["changelogs"])
        trimmed_packages += len(batch)
        batch.clear()
        update_total(trimmed_packages)
        print()
