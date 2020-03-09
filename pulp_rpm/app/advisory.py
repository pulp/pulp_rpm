from gettext import gettext as _
from itertools import chain

import hashlib

import createrepo_c as cr

from django.db import (
    IntegrityError,
    transaction,
)
from django.utils.dateparse import parse_datetime

from pulpcore.plugin.models import (
    Content,
    RepositoryContent,
)

from pulp_rpm.app.exceptions import AdvisoryConflict
from pulp_rpm.app.models import UpdateRecord


def resolve_advisories(version, previous_version):
    """
    Decide which advisories to add to a repo version and which to remove, and adjust a repo version.

    Args:
        version (pulpcore.app.models.RepositoryVersion): current incomplete repository version
        previous_version (pulpcore.app.models.RepositoryVersion):  a version preceding
                                                                   the current incomplete one

    """
    content_pks_to_add = set()
    content_pks_to_remove = set()
    content_pks_to_exclude = set()  # exclude from the set of content which is being added

    # identify conflicting advisories
    advisory_pulp_type = UpdateRecord.get_pulp_type()
    current_advisories = UpdateRecord.objects.filter(
        pk__in=version.content.filter(pulp_type=advisory_pulp_type))
    added_advisories = current_advisories
    advisory_conflicts = []
    if previous_version:
        previous_advisories = UpdateRecord.objects.filter(
            pk__in=previous_version.content.filter(pulp_type=advisory_pulp_type))
        previous_advisory_ids = set(previous_advisories.values_list('id', flat=True))

        # diff for querysets works fine but the result is not fully functional queryset,
        # e.g. filtering doesn't work
        added_advisories = current_advisories.difference(previous_advisories)
        if len(list(added_advisories)) != len(set(added_advisories)):
            raise AdvisoryConflict(_('It is not possible to add two advisories of the same id to '
                                     'a repository version.'))
        added_advisory_ids = set(adv.id for adv in added_advisories)
        advisory_conflicts = added_advisory_ids.intersection(previous_advisory_ids)

    added_advisory_pks = [adv.pk for adv in added_advisories]
    for advisory_id in advisory_conflicts:
        previous_advisory = previous_advisories.get(id=advisory_id)
        added_advisory = UpdateRecord.objects.get(id=advisory_id, pk__in=added_advisory_pks)
        to_add, to_remove, to_exclude = resolve_advisory_conflict(previous_advisory, added_advisory)
        content_pks_to_add.update(to_add)
        content_pks_to_remove.update(to_remove)
        content_pks_to_exclude.update(to_exclude)

    if content_pks_to_add:
        version.add_content(Content.objects.filter(pk__in=content_pks_to_add))

    if content_pks_to_remove:
        version.remove_content(Content.objects.filter(pk__in=content_pks_to_remove))

    if content_pks_to_exclude:
        RepositoryContent.objects.filter(
            repository=version.repository,
            content_id__in=content_pks_to_exclude,
            version_added=version
        ).delete()


def resolve_advisory_conflict(previous_advisory, added_advisory):
    """
    Decide which advisory to add to a repo version, create a new one if needed.

    No advisories with the same id can be present in a repo version.

    An existing advisory can be removed from a repo version, a newly added one can stay in a repo
    version, or advisories merge into newly created one which is added to a repo version.
    Merge is done based on criteria described below.

     1. If updated_dates are the same and pkglist intersection is empty (e.g. base repo merged
     with debuginfo repo) -> new UpdateRecord content unit with combined pkglist is created.
     2. If updated_dates differ and pkglist intersection is non-empty (update/re-sync/upload-new
     case) -> UpdateRecord with newer updated_date is added.
     3. If updated_dates differ and pkglist intersection is empty - ERROR CONDITION (e.g. base and
     -debuginfo repos are from different versions, not at same date)
     4. If update_dates are the same, pkglist intersection is non-empty and not equal to either
     pkglist - ERROR CONDITION! (never-happen case - "something is Terribly Wrong Here")

     TODO: Add version comparison if dates are the same (important for opensuse advisories)

     Args:
       previous_advisory(pulp_rpm.app.models.UpdateRecord): Advisory which is in a previous repo
                                                            version
       added_advisory(pulp_rpm.app.models.UpdateRecord): Advisory which is being added

     Returns:
       to_add(pulp_rpm.app.models.UpdateRecord): Advisory to add to a repo version, can be
                                                 a newly created one
       to_remove(pulp_rpm.app.models.UpdateRecord): Advisory to remove from a repo version
       to_exclude(pulp_rpm.app.models.UpdateRecord): Advisory to exclude from the added set of
                                                     content for a repo version

    """
    to_add, to_remove, to_exclude = [], [], []

    previous_updated_date = parse_datetime(
        previous_advisory.updated_date or previous_advisory.issued_date)
    added_updated_date = parse_datetime(
        added_advisory.updated_date or added_advisory.issued_date)

    previous_pkglist = set(previous_advisory.get_pkglist())
    added_pkglist = set(added_advisory.get_pkglist())

    if previous_updated_date == added_updated_date:
        if not previous_pkglist.intersection(added_pkglist):
            previous_advisory_pk = previous_advisory.pk
            added_advisory_pk = added_advisory.pk
            merged_advisory = merge_advisories(previous_advisory, added_advisory)
            to_add.append(merged_advisory.pk)
            to_remove.append(previous_advisory_pk)
            to_exclude.append(added_advisory_pk)
        else:
            raise AdvisoryConflict(_('Incoming and existing advisories have the same id and '
                                     'timestamp but different and intersecting package lists. '
                                     'At least one of them is wrong. '
                                     f'Advisory id: {previous_advisory.id}'))
    else:
        if previous_pkglist.intersection(added_pkglist):
            if previous_updated_date < added_updated_date:
                to_remove.append(previous_advisory.pk)
            else:
                to_exclude.append(added_advisory.pk)
        else:
            raise AdvisoryConflict(_('Incoming and existing advisories have the same id but '
                                     'different timestamps and intersecting package lists. It is '
                                     'likely that they are from two different incompatible remote '
                                     'repositories. E.g. RHELX-repo and RHELY-debuginfo repo. '
                                     'Ensure that you are adding content for the compatible '
                                     f'repositories. Advisory id: {previous_advisory.id}'))

    return to_add, to_remove, to_exclude


def merge_advisories(previous_advisory, added_advisory):
    """
    Create a new advisory with the merged pkglist.

    Args:
        previous_advisory(pulp_rpm.app.models.UpdateRecord): Advisory which is in a previous repo
                                                             version
        added_advisory(pulp_rpm.app.models.UpdateRecord): Advisory which is being added

    Returns:
        merged_advisory(pulp_rpm.app.models.UpdateRecord): Newly created Advisory with merged
                                                           package list from the other two ones.

    """
    previous_collections = previous_advisory.collections.all()
    added_collections = added_advisory.collections.all()
    references = previous_advisory.references.all()

    with transaction.atomic():
        merged_advisory_cr = previous_advisory.to_createrepo_c(
            collections=chain(previous_collections, added_collections))
        merged_digest = hash_update_record(merged_advisory_cr)
        merged_advisory = previous_advisory
        merged_advisory.pk = None
        merged_advisory.pulp_id = None
        merged_advisory.digest = merged_digest
        try:
            with transaction.atomic():
                merged_advisory.save()
        except IntegrityError:
            merged_advisory = UpdateRecord.objects.get(digest=merged_digest)
        else:
            for collection in chain(previous_collections, added_collections):
                merged_advisory.collections.add(collection)
            for reference in references:
                # copy reference and add relation for advisory
                reference.pk = None
                reference.save()
                merged_advisory.references.add(reference)

    return merged_advisory


def hash_update_record(update):
    """
    Find the hex digest for an update record xml from creatrepo_c.

    Args:
        update(createrepo_c.UpdateRecord): update record

    Returns:
        str: a hex digest representing the update record

    """
    uinfo = cr.UpdateInfo()
    uinfo.append(update)
    return hashlib.sha256(uinfo.xml_dump().encode('utf-8')).hexdigest()
