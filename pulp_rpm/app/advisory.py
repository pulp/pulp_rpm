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
from pulp_rpm.app.models import (
    UpdateCollectionPackage,
    UpdateRecord,
)
from pulp_rpm.app.shared_utils import is_previous_version


def resolve_advisories(version, previous_version):
    """
    Decide which advisories to add to a repo version and which to remove, and adjust a repo version.

    Advisory can be in 3 different states with relation to a repository version:
     - in-memory and added before this function call, so it's a part of the current incomplete
       repository version only
     - in the db, it's been added in some previous repository version
     - has no relation to any repository version because it's been created in this function as an
       outcome of conflict resolution.

    All 3 states need to be handled differently.
    The in-db ones and newly created are straightforward, just remove/add in a standard way.
    To remove in-memory ones (`content_pks_to_exclude`) from an incomplete repo version,
    one needs to do it directly from RepositoryContent. They've never been a part of a repo
    version, they are also not among the `content_pks_to_add` or `content_pks_to_remove` ones.

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

    # check for any conflict
    current_ids = [adv.id for adv in current_advisories]
    if previous_version and len(current_ids) != len(set(current_ids)):
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
            to_add, to_remove, to_exclude = resolve_advisory_conflict(
                previous_advisory, added_advisory
            )
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

     1. If updated_dates and update_version are the same and pkglist intersection is empty
     (e.g. base repo merged with debuginfo repo) -> new UpdateRecord content unit with combined
     pkglist is created.
     2. If updated_dates or update_version differ and pkglist intersection is non-empty
     (update/re-sync/upload-new case) -> UpdateRecord with newer updated_date or update_version
     is added.
     3. If updated_dates differ and pkglist intersection is empty: ERROR CONDITION
     (e.g. base and-debuginfo repos are from different versions, not at same date)
     4. If update_dates and update_version are the same, pkglist intersection is non-empty
     and not equal to either pkglist - ERROR CONDITION!
     (never-happen case - "something is Terribly Wrong Here")

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
        previous_advisory.updated_date or previous_advisory.issued_date
    )
    added_updated_date = parse_datetime(
        added_advisory.updated_date or added_advisory.issued_date
    )
    previous_updated_version = previous_advisory.version
    added_updated_version = added_advisory.version
    previous_pkglist = set(previous_advisory.get_pkglist())
    added_pkglist = set(added_advisory.get_pkglist())

    # Prepare results of conditions for easier use.
    same_dates = previous_updated_date == added_updated_date
    same_version = previous_updated_version == added_updated_version
    pkgs_intersection = previous_pkglist.intersection(added_pkglist)

    if same_dates and same_version and pkgs_intersection:
        if previous_pkglist != added_pkglist:
            raise AdvisoryConflict(_('Incoming and existing advisories have the same id and '
                                     'timestamp but different and intersecting package lists. '
                                     'At least one of them is wrong. '
                                     f'Advisory id: {previous_advisory.id}'))
        elif previous_pkglist == added_pkglist:
            # it means some advisory metadata changed without bumping the updated_date or version.
            # There is no way to find out which one is newer, and a user can't fix it,
            # so we are choosing the incoming advisory.
            to_remove.append(previous_advisory.pk)
    elif (not same_dates and not pkgs_intersection) or \
            (same_dates and not same_version and not pkgs_intersection):
        raise AdvisoryConflict(_('Incoming and existing advisories have the same id but '
                                 'different timestamps and intersecting package lists. It is '
                                 'likely that they are from two different incompatible remote '
                                 'repositories. E.g. RHELX-repo and RHELY-debuginfo repo. '
                                 'Ensure that you are adding content for the compatible '
                                 f'repositories. Advisory id: {previous_advisory.id}'))
    elif not same_dates and pkgs_intersection:
        if previous_updated_date < added_updated_date:
            to_remove.append(previous_advisory.pk)
        else:
            to_exclude.append(added_advisory.pk)
    elif not same_version and pkgs_intersection:
        if is_previous_version(previous_updated_version, added_updated_version):
            to_remove.append(previous_advisory.pk)
        else:
            to_exclude.append(added_advisory.pk)
    elif same_dates and same_version and not pkgs_intersection:
        # previous_advisory is used to copy the object and thus the variable refers to a
        # different object after `merge_advisories` call
        previous_advisory_pk = previous_advisory.pk
        merged_advisory = merge_advisories(previous_advisory, added_advisory)
        to_add.append(merged_advisory.pk)
        to_remove.append(previous_advisory_pk)
        to_exclude.append(added_advisory.pk)

    return to_add, to_remove, to_exclude


def _copy_update_collections_for(advisory, collections):
    """
    Deep-copy each UpdateCollection in the_collections, and assign to its new advisory.
    """
    new_collections = []
    with transaction.atomic():
        for collection in collections:
            uc_packages = collection.packages.all()
            collection.pk = None
            collection.update_record = advisory
            collection.save()
            new_packages = []
            for a_package in uc_packages:
                a_package.pk = None
                a_package.update_collection = collection
                new_packages.append(a_package)
            UpdateCollectionPackage.objects.bulk_create(new_packages)
            new_collections.append(collection)
    return new_collections


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
        # First thing to do is ensure collection-name-uniqueness
        # in the newly-merged advisory.

        # dictionary of collection-name:first-unused-suffix pairs
        names_seen = {}
        for collection in chain(previous_collections, added_collections):
            # If we've seen a collection-name already, create a new name
            # by appending "_<suffix>" and rename the collection before
            # merging
            if collection.name in names_seen.keys():
                orig_name = collection.name
                new_name = f"{orig_name}_{names_seen[orig_name]}"
                names_seen[orig_name] += 1
                collection.name = new_name
            # if we've not seen it before, store in names-seen as name:0
            else:
                names_seen[collection.name] = 0
        merged_advisory_cr = previous_advisory.to_createrepo_c(
            collections=chain(previous_collections, added_collections))
        merged_digest = hash_update_record(merged_advisory_cr)
        merged_advisory = previous_advisory
        # Need to null both pk (content_ptr_id) and pulp_id here to insure django doesn't
        # find the original advisory instead of making a copy for us
        merged_advisory.pk = None
        merged_advisory.pulp_id = None
        merged_advisory.digest = merged_digest
        try:
            with transaction.atomic():
                merged_advisory.save()
        except IntegrityError:
            merged_advisory = UpdateRecord.objects.get(digest=merged_digest)
        else:
            # For UpdateCollections, make sure we don't re-use the collections for either of the
            # advisories being merged
            _copy_update_collections_for(merged_advisory, chain(previous_collections,
                                                                added_collections))
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
