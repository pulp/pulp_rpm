import uuid
from gettext import gettext as _

import rpm_rs
from django.core.management import BaseCommand, CommandError
from django.db.models import Exists, F, OuterRef, Value
from django.db.models.functions import Concat

from pulpcore.plugin.models import ContentArtifact

from pulp_rpm.app.models import Package  # noqa
from pulp_rpm.app.models.advisory import UpdateCollection, UpdateRecord  # noqa
from pulp_rpm.app.models.repository import RpmRepository  # noqa
from pulp_rpm.app.shared_utils import format_signing_keys


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
            help=_("Don't make any changes, just print diagnostics."),
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
        elif issue == "4073":
            self.repair_4073(dry_run)
        elif issue == "4458":
            self.repair_4458(dry_run)
        else:
            raise CommandError(_("Unknown issue: '{}'").format(issue))

    def repair_2460(self, dry_run):
        """Perform data repair for issue #2460."""

        def fix_package(package):
            def fix_requirement(require):
                name, flags, epoch, version, release, pre = require
                if "&#38;#38;" in name:
                    fixed_name = name.replace("&#38;#38;", "&")
                    return (fixed_name, flags, epoch, version, release)
                else:
                    return require

            package.requires = [fix_requirement(require) for require in package.provides]
            package.save()

        # This is the only known affected package, we can update this later if we find more.
        packages = Package.objects.filter(name="bpg-algeti-fonts")

        for package in packages:
            if not dry_run:
                self.stdout.write(
                    f"Fixing requirement for package '{package.nevra}' ({package.pk})"
                )
                fix_package(package)
            else:
                self.stdout.write(
                    f"Package '{package.nevra}' ({package.pk}) has broken requirement"
                )

    def repair_3127(self, dry_run):
        """Perform data repair for issue #3127."""
        update_collections = UpdateCollection.objects.exclude(name__isnull=False)
        for collection in update_collections:
            if not dry_run:
                self.stdout.write(f"Fixing missing name for UpdateCollection ({collection.pk})")
                collection.name = "collection-autofill-" + uuid.uuid4().hex[:12]
                collection.save()
            else:
                self.stdout.write(f"UpdateCollection ({collection.pk}) has missing name")

    def repair_4007(self, dry_run):
        """Perform data repair for issue #4007."""
        affected = RpmRepository.objects.filter(package_signing_fingerprint="")
        count = affected.count()
        if not dry_run:
            affected.update(package_signing_fingerprint=None)
            self.stdout.write(f"Fixed {count} repositories with empty package_signing_fingerprint.")
        else:
            self.stdout.write(f"{count} repositories have an empty package_signing_fingerprint.")

    def repair_4073(self, dry_run):
        """Perform data repair for issue #4073.

        For each updated ContentArtifact, print:
            {package_uuid} {ca_uuid} {old_relpath} {new_relpath}
        """
        update_count = 0
        skipped_count = 0
        batch = []
        batch_msgs = []

        def process_batch():
            nonlocal update_count, batch, batch_msgs
            if not dry_run:
                ContentArtifact.objects.bulk_update(batch, fields=["relative_path"])
            for msg in batch_msgs:
                self.stdout.write(msg)
            self.stdout.flush()
            update_count += len(batch)
            batch.clear()
            batch_msgs.clear()

        def add_to_batch(ca):
            original_relpath = ca.relative_path
            ca.relative_path = ca.expected_filename
            batch.append(ca)
            batch_msgs.append(
                UPDATE_MSG.format(
                    pkg_uuid=str(ca.content_id),
                    ca_uuid=str(ca.pk),
                    old_relpath=original_relpath,
                    new_relpath=ca.relative_path,
                )
            )

        sibling_cas = ContentArtifact.objects.filter(content_id=OuterRef("content_id")).exclude(
            pk=OuterRef("pk")
        )
        bad_content_artifacts = (
            ContentArtifact.objects.filter(
                content__pulp_type=Package.get_pulp_type(),
                content__rpm_package__isnull=False,
            )
            .annotate(
                expected_filename=Concat(
                    F("content__rpm_package__name"),
                    Value("-"),
                    F("content__rpm_package__version"),
                    Value("-"),
                    F("content__rpm_package__release"),
                    Value("."),
                    F("content__rpm_package__arch"),
                    Value(".rpm"),
                ),
                has_sibling=Exists(sibling_cas),
            )
            .exclude(relative_path=F("expected_filename"))
            .order_by("content_id", "pk")
        )

        UPDATE_MSG = "{pkg_uuid!r} {ca_uuid!r} {old_relpath!r} {new_relpath!r}"
        for ca in bad_content_artifacts.iterator(chunk_size=1000):
            if ca.has_sibling:
                skipped_count += 1
                self.stdout.write(
                    f"Skipping package {ca.content_id!r}: multiple ContentArtifacts make "
                    f"normalizing {ca.relative_path!r} to {ca.expected_filename!r} ambiguous."
                )
                continue

            add_to_batch(ca)
            if len(batch) >= 500:
                process_batch()
        if batch:
            process_batch()

        verb = "Would update" if dry_run else "Updated"
        self.stdout.write(f"{verb} {update_count} records")
        if skipped_count:
            self.stdout.write(f"Skipped {skipped_count} records due to ContentArtifact conflicts")

    def repair_4458(self, dry_run):
        """Perform data repair for issue #4458.

        Backfill signing_keys for packages that were synced before signature
        extraction was implemented. Reads only the RPM metadata headers (not the
        payload) to extract signature fingerprints.
        """
        packages = Package.objects.filter(signing_keys=None)
        total = packages.count()
        self.stdout.write(f"Found {total} packages with signing_keys=NULL")

        if dry_run or total == 0:
            return

        batch = []
        update_count = 0

        def process_batch():
            nonlocal update_count, batch
            Package.objects.bulk_update(batch, fields=["signing_keys"])
            update_count += len(batch)
            self.stdout.write(f"  updated {update_count}/{total}")
            batch.clear()

        for package in packages.iterator():
            ca = package.contentartifact_set.select_related("artifact").first()
            if ca is None or ca.artifact is None:
                continue

            artifact = ca.artifact
            storage = artifact.pulp_domain.get_storage()
            artifact_file = storage.open(storage.get_artifact_path(artifact.sha256))
            try:
                header_bytes = artifact_file.read(package.rpm_header_end)
            finally:
                artifact_file.close()
            metadata = rpm_rs.PackageMetadata.from_bytes(header_bytes)

            package.signing_keys = format_signing_keys(metadata.signatures())
            batch.append(package)
            if len(batch) >= 500:
                process_batch()

        if batch:
            process_batch()
        self.stdout.write(f"Updated {update_count} packages")
