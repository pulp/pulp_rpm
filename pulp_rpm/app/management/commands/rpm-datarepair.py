from gettext import gettext as _

from django.core.management import BaseCommand, CommandError

from pulp_rpm.app.models import Package  # noqa
from pulp_rpm.app.shared_utils import read_crpackage_from_artifact


class Command(BaseCommand):
    """
    Django management command for repairing RPM metadata in the Pulp database.
    """

    help = _(__doc__)

    def add_arguments(self, parser):
        """Set up arguments."""
        parser.add_argument("issue", help=_("The github issue # of the issue to be fixed."))
        parser.add_argument("-y", "--yes", action='store_true', default=False,
                            help=_('Execute change with no "Are you sure?" prompt.'))

    def handle(self, *args, **options):
        """Implement the command."""
        issue = options["issue"]

        if issue == "2460":
            self.repair_2460()
        elif issue == "2258":
            self.repair_2258(options["yes"])
        else:
            raise CommandError(_("Unknown issue: '{}'").format(issue))

    def repair_2258(self, execute=False):
        """Re-examine package header and store signing key for issue #2258."""
        if not execute:
            count = Package.objects.filter(signer_key_id__isnull=True).count()
            print(f"This will require downloading {count} packages out of storage for examination, "
                  "which may be time-and-cost expensive. Are you sure you want to do that? Run "
                  'again with "--yes" to proceed.')
            return

        packages = Package.objects.filter(signer_key_id__isnull=True).iterator()
        for package in packages:
            _, pub_key_id = read_crpackage_from_artifact(package._artifacts.first())  # Only one.
            if pub_key_id is not None:
                print(f"Fixing stored signature for {package.nevra}")
                package.signer_key_id = pub_key_id
                package.save()

    def repair_2460(self):
        """Perform data repair for issue #2460."""

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
