from gettext import gettext as _
from collections import defaultdict
from itertools import chain

import hashlib

import createrepo_c as cr
from datetime import datetime

from django.conf import settings
from django.db import (
    IntegrityError,
    transaction,
)
from django.utils.dateparse import parse_datetime

from pulpcore.plugin.models import Content

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
    # identify conflicting advisories
    advisory_pulp_type = UpdateRecord.get_pulp_type()
    current_advisories = UpdateRecord.objects.filter(
        pk__in=version.content.filter(pulp_type=advisory_pulp_type)
    )

    # check for any conflict
    unique_advisory_ids = {adv.id for adv in current_advisories}
    if len(current_advisories) == len(unique_advisory_ids):
        # no conflicts
        return

    current_advisories_by_id = defaultdict(list)
    for advisory in current_advisories:
        current_advisories_by_id[advisory.id].append(advisory)

    if previous_version:
        previous_advisories = UpdateRecord.objects.filter(
            pk__in=previous_version.content.filter(pulp_type=advisory_pulp_type)
        )
        previous_advisory_ids = set(previous_advisories.values_list("id", flat=True))

        # diff for querysets works fine but the result is not fully functional queryset,
        # e.g. filtering doesn't work
        added_advisories = current_advisories.difference(previous_advisories)
        added_advisories_by_id = defaultdict(list)
        for advisory in added_advisories:
            added_advisories_by_id[advisory.id].append(advisory)
    else:
        previous_advisory_ids = set()
        added_advisories = current_advisories
        added_advisories_by_id = current_advisories_by_id

    # Conflicts can be in different places and behaviour differs based on that.
    # `in_added`, when conflict happens in the added advisories, this is not allowed and
    # should fail.
    # `added_vs_previous`, a standard conflict between an advisory which is being added and the one
    # in the preceding repo version. This should be resolved according to the heuristics,
    # unless previous repo version has conflicts. In the latter case, the added advisory is picked.
    advisory_id_conflicts = {"in_added": [], "added_vs_previous": []}
    for advisory_id, advisories in current_advisories_by_id.items():
        # we are only interested in conflicts where added advisory is present, we are not trying
        # to fix old conflicts in the existing repo version. There is no real harm in htose,
        # just confusing.
        if len(advisories) > 1 and advisory_id in added_advisories_by_id:
            # if the conflict is in added advisories (2+ advisories with the same id are being
            # added), we need to collect such ids to fail later with
            # a list of all conflicting advisories. No other processing of those is needed.
            if len(added_advisories_by_id[advisory_id]) > 1:
                advisory_id_conflicts["in_added"].append(advisory_id)
            # a standard conflict is detected
            elif advisory_id in previous_advisory_ids:
                advisory_id_conflicts["added_vs_previous"].append(advisory_id)

    content_pks_to_add = set()
    content_pks_to_remove = set()
    content_pks_to_exclude = set()  # exclude from the set of content which is being added

    # Incoming has duplicates - merge till There Is Only One
    for adv_id in advisory_id_conflicts["in_added"]:
        conflict_advisories = current_advisories_by_id[adv_id]
        new_advisory = conflict_advisories[0]
        tmp_advisories = []
        for adv in conflict_advisories[1:]:
            pk_to_add, pk_to_remove, pk_to_exclude = resolve_advisory_conflict(new_advisory, adv)
            if pk_to_add:
                new_advisory = UpdateRecord.objects.filter(pk=pk_to_add[0]).get()
                tmp_advisories.append(new_advisory)
            # If the first duplicate advisory is ended up in to_remove or to_exclude then
            # set the one it was compared against as the one to keep.
            # See https://github.com/pulp/pulp_rpm/pull/3588
            elif new_advisory.pk in pk_to_remove or new_advisory.pk in pk_to_exclude:
                new_advisory = adv
            content_pks_to_exclude.update(pk_to_exclude)
            content_pks_to_remove.update(pk_to_remove)
        added_advisories_by_id[adv_id] = [new_advisory]
        content_pks_to_add.add(new_advisory.pk)
        for tmp_adv in tmp_advisories[:-1]:  # Keep only the last added advisory
            tmp_adv.delete()

    # Incoming has a duplicate advisory-id to previous - resolve
    for advisory_id in advisory_id_conflicts["added_vs_previous"]:
        previous_advisory_qs = previous_advisories.filter(id=advisory_id)
        # there can only be one added advisory at this point otherwise the AdvisoryConflict
        # would have been raised by now
        added_advisory = added_advisories_by_id[advisory_id][0]
        added_advisory.touch()
        if previous_advisory_qs.count() > 1:
            # due to an old bug there could be N advisories with the same id in a repo,
            # this is wrong and there may not be a good way to resolve those, so let's take the
            # new one.
            content_pks_to_add.update([added_advisory.pk])
            content_pks_to_remove.update([adv.pk for adv in previous_advisory_qs])
        else:
            to_add, to_remove, to_exclude = resolve_advisory_conflict(
                previous_advisory_qs.first(), added_advisory
            )
            content_pks_to_add.update(to_add)
            content_pks_to_remove.update(to_remove)
            content_pks_to_exclude.update(to_exclude)

    if content_pks_to_add:
        version.add_content(Content.objects.filter(pk__in=content_pks_to_add))

    if content_pks_to_remove:
        version.remove_content(Content.objects.filter(pk__in=content_pks_to_remove))

    if content_pks_to_exclude:
        version.remove_content(Content.objects.filter(pk__in=content_pks_to_exclude))


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

     3. If updated_dates differ and pkglist intersection is empty:
       3.a If pklists differ only IN EVR (ie, name-intersection is Not Empty) -> use-newer
       3.b else -> ERROR CONDITION
         (e.g. base and-debuginfo repos are from different versions, not at same date)

     4. If update_dates and update_version are the same, pkglist intersection is non-empty
     and not a proper subset of to either pkglist - ERROR CONDITION!
     (never-happen case - "something is Terribly Wrong Here")

     Args:
       previous_advisory(pulp_rpm.app.models.UpdateRecord): Advisory which is in a previous repo
                                                            version
       added_advisory(pulp_rpm.app.models.UpdateRecord): Advisory which is being added

     Returns:
       to_add(list): UUIDs of advisories to add to a repo version, can be newly created ones
       to_remove(list): UUIDs of advisories to remove from a repo version
       to_exclude(list): UUIDs of advisories to exclude from the added set of content for a repo
                                  version

    """

    def _datetime_heuristics(in_str):
        # issue- and update-dates can be datetimes, empty, or timetamps. Alas.
        # Try to Do The Right Thing.
        # Return None if we give up
        if not in_str:
            return None

        dt = parse_datetime(in_str)
        if not dt:
            try:
                tstamp = int(in_str)
                dt = datetime.fromtimestamp(tstamp)
            except:  # noqa
                # No idea what this is - give up and return None
                return None
        return dt

    def _do_merge():
        # previous_advisory is used to copy the object and thus the variable refers to a
        # different object after `merge_advisories` call
        previous_advisory_pk = previous_advisory.pk
        merged_advisory = merge_advisories(previous_advisory, added_advisory)
        to_add.append(merged_advisory.pk)
        to_remove.append(previous_advisory_pk)
        to_exclude.append(added_advisory.pk)

    def _name_intersect(prev_pkgs, new_pkgs):
        prev_names = set([x[0] for x in prev_pkgs])
        new_names = set([x[0] for x in new_pkgs])
        return prev_names.intersection(new_names)

    to_add, to_remove, to_exclude = [], [], []

    previous_updated_date = _datetime_heuristics(
        previous_advisory.updated_date or previous_advisory.issued_date
    )
    added_updated_date = _datetime_heuristics(
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
    names_intersection = _name_intersect(previous_pkglist, added_pkglist)

    if same_dates and same_version and pkgs_intersection:
        if previous_pkglist != added_pkglist:
            # prev and new have different pkg-lists. See if one is a proper-subset of the other;
            # if so, choose the one with the *larger* pkglist. Otherwise, error.
            if previous_pkglist < added_pkglist:
                # new has more pkgs - remove previous
                to_remove.append(previous_advisory.pk)
            elif added_pkglist < previous_pkglist:
                # prev has more pkgs - exclude new
                to_exclude.append(added_advisory.pk)
            else:
                if settings.ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION:
                    _do_merge()
                else:
                    raise AdvisoryConflict(
                        _(
                            "Incoming and existing advisories have the same id and timestamp "
                            "but different and intersecting package lists, "
                            "and neither package list is a proper subset of the other. "
                            "At least one of the advisories is wrong. "
                            "To allow this behavior, set "
                            "ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION = True (q.v.) "
                            "in your configuration. Advisory id: {}"
                        ).format(previous_advisory.id)
                    )
        elif previous_pkglist == added_pkglist:
            # it means some advisory metadata changed without bumping the updated_date or version.
            # There is no way to find out which one is newer, and a user can't fix it,
            # so we are choosing the incoming advisory.
            to_remove.append(previous_advisory.pk)
    elif (not same_dates or (same_dates and not same_version)) and not pkgs_intersection:
        if names_intersection or settings.ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION:
            # Keep "newer" advisory
            if not same_dates:
                if previous_updated_date < added_updated_date:
                    to_remove.append(previous_advisory.pk)
                else:
                    to_exclude.append(added_advisory.pk)
            elif not same_version:
                if is_previous_version(previous_updated_version, added_updated_version):
                    to_remove.append(previous_advisory.pk)
                else:
                    to_exclude.append(added_advisory.pk)
        else:
            raise AdvisoryConflict(
                _(
                    "Incoming and existing advisories have the same id but "
                    "different timestamps and non-intersecting package lists. "
                    "It is likely that they are from two different incompatible remote "
                    "repositories. E.g. RHELX-repo and RHELY-debuginfo repo. "
                    "Ensure that you are adding content for the compatible repositories. "
                    "To allow this behavior, set "
                    "ALLOW_AUTOMATIC_UNSAFE_ADVISORY_CONFLICT_RESOLUTION = True (q.v.) "
                    "in your configuration. Advisory id: {}"
                ).format(previous_advisory.id)
            )
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
        _do_merge()

    return to_add, to_remove, to_exclude


def _copy_update_collections_for(advisory, collections):
    """
    Deep-copy each UpdateCollection in the_collections, and assign to its new advisory.
    """
    new_collections = []
    with transaction.atomic():
        for collection in collections:
            uc_packages = list(collection.packages.all())
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

    # First thing to do is ensure collection-name-uniqueness
    # in the newly-merged advisory.

    # If we've seen a collection-name already, create a new name
    # by appending "_<index>" and rename the collection before
    # merging.
    # "index", in this context, is a monotonically-increasing INTEGER. In the code below, note
    # the lines that insure that, when a new "index" is required, choosing (curr-max+1) is
    # guaranteed.
    # NOTE: keeping the collections separate is DELIBERATE:
    # 1) after the fact, it's clear that an advisory merge happened, and that one set of
    #    packages comes from one place, one from a different one
    # 2) package-grouping can be *relevant* (e.g. base-rpms vs debuginfo-rpms)
    # 3) package-grouping can be *required* (e.g., module-collections must be kept separate)

    def get_new_name(collection, collection_group):
        """
        Generate a new collection-name based on the current one and a list of "indexes".

        Collections are unique-ified by adding "_INTEGER" to their given names.
        Collection-group is keyed by "original" name, with values of "all index-integers seen
          so far".
        New names are coined as "original name + max(index-integers seen so far for that name".
        """
        name_list = collection.name.split("_")
        if name_list[-1].isdecimal():
            name_list.pop(-1)
            orig_name = "_".join(name_list)
        else:
            orig_name = collection.name

        if orig_name in collection_group.keys():
            index = max(collection_group[orig_name]) + 1
        else:
            index = 0
        collection_group.setdefault(orig_name, []).append(index)
        return f"{orig_name}_{index}"

    # Set up the "collection-group" to an initial state - all the current-names, and a list
    # of any "indices" they've been given, so we can know what our current-max-index is
    # before we start renaming collections.
    collection_group = {}
    for collection in chain(previous_collections, added_collections):
        # It's possible for a collection to have NO NAME (not even an empty string)
        if not collection.name:
            collection.name = ""
        name_list = collection.name.split("_")
        if name_list[-1].isdecimal():
            index = name_list.pop(-1)
            orig_name = "_".join(name_list)
            collection_group.setdefault(orig_name, []).append(int(index))

    # Now, prepare for, and merge, the two advisories
    with transaction.atomic():
        # Finalize unique-ified collection names, to use in the event of concurrency-collisions
        # if a collection has no name, we assign it the name "collection".
        names_seen = ["collection"]
        collections_to_merge = set([])
        for collection in chain(previous_collections, added_collections):
            # No packages? ignore
            if collection.packages.count() == 0:
                continue

            # no-name? When merging, ILLEGAL! Give it a name
            if not collection.name:
                collection.name = "collection"

            # If we've seen a collection with "this" name - give it a unique one,
            # and add that name to the "seen" list
            if collection.name in names_seen:
                collection.name = get_new_name(collection, collection_group)
            # Either we've not seen it ever, or we've generated a new "indexed" name
            names_seen.append(collection.name)
            # add the collection to the "set of collections for the merged advisory"
            collections_to_merge.add(collection)

        # Compute digest for the new merged advisory and save it
        merged_advisory_cr = previous_advisory.to_createrepo_c(collections=collections_to_merge)
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
            merged_advisory.touch()
        else:
            # For UpdateCollections, make sure we don't re-use the collections for either of the
            # advisories being merged
            _copy_update_collections_for(merged_advisory, collections_to_merge)
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
    return hashlib.sha256(uinfo.xml_dump().encode("utf-8")).hexdigest()
