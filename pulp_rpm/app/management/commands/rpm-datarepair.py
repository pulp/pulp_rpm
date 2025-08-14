import uuid
from gettext import gettext as _

from django.core.management import BaseCommand, CommandError

from django.db.models import F, Value
from django.db.models.functions import Concat
from pulp_rpm.app.models import Package  # noqa
from pulp_rpm.app.models.advisory import UpdateCollection, UpdateRecord  # noqa
from pulpcore.plugin.models import ContentArtifact


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
        elif issue == "3127":
            self.repair_3127()
        elif issue == "4073":
            self.repair_4073()
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

    def repair_3127(self):
        """Perform data repair for issue #3127."""
        update_collections = UpdateCollection.objects.exclude(name__isnull=False)
        for collection in update_collections:
            collection.name = "collection-autofill-" + uuid.uuid4().hex[:12]
            collection.save()

    def repair_4073(self):
        """Perform data repair for issue #4073.

        For each updated ContentArtifact, print:
            {ca.pkg_uuid} {ca_uuid} {old_relpath} {new_relpath}
        """
        update_count = 0
        batch = []
        batch_msgs = []

        def process_batch():
            nonlocal update_count, batch, batch_msgs
            ContentArtifact.objects.bulk_update(batch, fields=["relative_path"])
            for msg in batch_msgs:
                self.stdout.write(msg)
            self.stdout.flush()
            update_count += len(batch)
            batch.clear()
            batch_msgs.clear()

        def add_to_batch(ca, pkg):
            original_relpath = ca.relative_path
            ca.relative_path = pkg.filename
            batch.append(ca)
            batch_msgs.append(
                UPDATE_MSG.format(
                    pkg_uuid=str(pkg.pk),
                    ca_uuid=str(ca.pk),
                    old_relpath=original_relpath,
                    new_relpath=ca.relative_path,
                )
            )

        bad_packages = Package.objects.annotate(
            computed_filename=Concat(
                F("name"),
                Value("-"),
                F("version"),
                Value("-"),
                F("release"),
                Value("."),
                F("arch"),
                Value(".rpm"),
            )
        ).exclude(location_href__endswith=F("computed_filename"))

        UPDATE_MSG = "{pkg_uuid!r} {ca_uuid!r} {old_relpath!r} {new_relpath!r}"
        for pkg in bad_packages.iterator():
            for ca in pkg.contentartifact_set.exclude(relative_path=pkg.filename):
                add_to_batch(ca, pkg)
                if len(batch) > 500:
                    process_batch()
        if batch:  # handle remaining
            process_batch()
        self.stdout.write(f"Updated {update_count} records")
