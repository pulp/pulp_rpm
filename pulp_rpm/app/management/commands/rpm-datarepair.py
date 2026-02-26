import uuid
from gettext import gettext as _

from django.core.management import BaseCommand, CommandError

from pulp_rpm.app.models import Package  # noqa
from pulp_rpm.app.models.advisory import UpdateCollection, UpdateRecord  # noqa
from pulp_rpm.app.models.repository import RpmRepository  # noqa


def raise_if_dry_run(issue, dry_run):
    if dry_run:
        raise CommandError(_("--dry-run is not supported for issue #{}.").format(issue))


class Command(BaseCommand):
    """
    Django management command for repairing RPM metadata in the Pulp database.
    """

    help = _(__doc__)

    def add_arguments(self, parser):
        """Set up arguments."""
        parser.add_argument("issue", help=_("The github issue # of the issue to be fixed."))
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=_("Run without making changes."),
        )

    def handle(self, *args, **options):
        """Implement the command."""
        issue = options["issue"]
        dry_run = options["dry_run"]

        if issue == "2460":
            self.repair_2460(dry_run)
        elif issue == "3127":
            self.repair_3127(dry_run)
        elif issue == "4007":
            self.repair_4007(dry_run)
        else:
            raise CommandError(_("Unknown issue: '{}'").format(issue))

    def repair_2460(self, dry_run):
        """Perform data repair for issue #2460."""
        raise_if_dry_run("2460", dry_run)

        def fix_package(package):
            def fix_requirement(require):
                (name, flags, epoch, version, release, pre) = require
                if "&#38;#38;" in name:
                    fixed_name = name.replace("&#38;#38;", "&")
                    return (fixed_name, flags, epoch, version, release)
                else:
                    return require

            package.requires = [fix_requirement(require) for require in package.provides]

        # This is the only known affected package, we can update this later if we find more.
        packages = Package.objects.filter(name="bpg-algeti-fonts")

        for package in packages:
            fix_package(package)
            package.save()

    def repair_3127(self, dry_run):
        """Perform data repair for issue #3127."""
        raise_if_dry_run("3127", dry_run)
        update_collections = UpdateCollection.objects.exclude(name__isnull=False)
        for collection in update_collections:
            collection.name = "collection-autofill-" + uuid.uuid4().hex[:12]
            collection.save()

    def repair_4007(self, dry_run):
        """Perform data repair for issue #4007."""
        affected = RpmRepository.objects.filter(package_signing_fingerprint="")
        count = affected.count()
        if not dry_run:
            affected.update(package_signing_fingerprint=None)
            self.stdout.write(f"Fixed {count} repositories with empty package_signing_fingerprint.")
        else:
            self.stdout.write(f"{count} repositories have an empty package_signing_fingerprint.")
