from gettext import gettext as _

from django.core.management import BaseCommand, CommandError

from pulp_rpm.app.models import Package, UpdateCollectionPackage  # noqa


class Command(BaseCommand):
    """
    Django management command for repairing RPM metadata in the Pulp database.
    """

    help = _(__doc__)

    def add_arguments(self, parser):
        """Set up arguments."""
        parser.add_argument("issue", help=_("The github issue # of the issue to be fixed."))

    def handle(self, *args, **options):
        """Implement the command."""
        issue = options["issue"]

        if issue == "2460":
            self.repair_2460()
        elif issue == "2754":
            self.repair_2754()
        else:
            raise CommandError(_("Unknown issue: '{}'").format(issue))

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

    def repair_2754(self):
        """Perform datarepair for issue #2754."""

        duplicate_pks = set()

        package_query = UpdateCollectionPackage.objects.all()

        for ucp in package_query:
            q = package_query.filter(
                name=ucp.name,
                epoch=ucp.epoch,
                version=ucp.version,
                release=ucp.release,
                arch=ucp.arch,
                filename=ucp.filename,
                update_collection=ucp.update_collection,
            )
            if len(q) > 1:
                for pkg in q[1:]:
                    duplicate_pks.add(pkg.pk)

        if input(
            f"Are you sure to remove {len(duplicate_pks)} duplicated advisory packages? (y/N) "
        ) in ["Y", "y"]:
            UpdateCollectionPackage.objects.filter(pk__in=duplicate_pks).delete()
