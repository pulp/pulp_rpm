"""
SHA and SHA-1 are the same checksum type, but remote feeds aren't consistent about which label they
use for the type. Pulp didn't consider these to be the same type, which caused problems during Node
publishes.

This migration searches for units that use "sha" as the checksum type. For each that it finds, it
attempts to change the checksumtype to "sha1". If this is successful, nothing more needs to be done.
However, if there is already a unit with identical NEVRA and checksum this will cause a uniqueness
conflict. In this case, it is necessary to find references to the "sha" unit and alter them to use
the "sha1" unit. After this, it deleted the "sha" unit.

https://bugzilla.redhat.com/show_bug.cgi?id=1165355
"""
from gettext import gettext as _
import logging

from pymongo import errors

from pulp.plugins.util import verification
from pulp.server.db import connection


_logger = logging.getLogger(__name__)


def migrate(*args, **kwargs):
    """
    Make sure that we don't have any RPMs with a checksumtype of "sha".

    :param args:   Unused
    :type  args:   list
    :param kwargs: Unused
    :type  kwargs: dict
    """
    for unit_type in ('drpm', 'rpm', 'srpm'):
        _migrate_rpmlike_units(unit_type)
    _migrate_yum_metadata_files()
    _migrate_errata()


def _migrate_errata():
    """
    Visit each errata and check its references RPMs for the checksum type, sanitizing it if
    necessary. Since these sums aren't part of the unit key for erratum, this will not cause any
    collisions. The erratum also do not reference RPMs by unit_id, but by unit_key, so this is
    important.
    """
    errata = connection.get_collection('units_erratum')
    for erratum in errata.find():
        changed = False
        pkglist = erratum.get('pkglist', [])
        for collection in pkglist:
            for package in collection.get('packages', []):
                if package['sum']:
                    sanitized_type = verification.sanitize_checksum_type(package['sum'][0])
                    if sanitized_type != package['sum'][0]:
                        package['sum'][0] = sanitized_type
                        changed = True
        if changed:
            errata.update({'_id': erratum['_id']},
                          {'$set': {'pkglist': pkglist}})


def _migrate_rpmlike_units(unit_type):
    """
    This function performs the migration on RPMs, DRPMs, and SRPMs. These all have the same schema
    when it comes to checksumtype, so they can be treated the same way.

    :param unit_type:          The unit_type_id, as found in pulp_rpm.common.ids.
    :type  unit_type:          basestring
    """
    repos = connection.get_collection('repos')
    repo_content_units = connection.get_collection('repo_content_units')
    unit_collection = connection.get_collection('units_%s' % unit_type)

    for unit in unit_collection.find():
        try:
            sanitized_type = verification.sanitize_checksum_type(unit['checksumtype'])
            if sanitized_type != unit['checksumtype']:
                # Let's see if we can get away with changing its checksumtype to the sanitized
                # value. If this works, we won't have to do anything else.
                unit_collection.update({'_id': unit['_id']},
                                       {'$set': {'checksumtype': sanitized_type}})
        except errors.DuplicateKeyError:
            # Looks like there is already an identical unit with the sanitized checksum type. This
            # means we need to remove the current unit, but first we will need to change any
            # references to this unit to point to the other.
            conflicting_unit = unit_collection.find_one(
                {'name': unit['name'], 'epoch': unit['epoch'], 'version': unit['version'],
                 'release': unit['release'], 'arch': unit['arch'], 'checksum': unit['checksum'],
                 'checksumtype': sanitized_type})
            for rcu in repo_content_units.find({'unit_type_id': unit_type, 'unit_id': unit['_id']}):
                # Now we must either switch the rcu from pointing to unit to pointing to
                # conflicting_unit, or delete the rcu if there is already one in the same repo.
                try:
                    msg = _('Updating %(repo_id)s to contain %(type)s %(conflicting)s instead of '
                            '%(old_id)s.')
                    msg = msg % {'repo_id': rcu['repo_id'], 'type': unit_type,
                                 'conflicting': conflicting_unit['_id'], 'old_id': unit['_id']}
                    _logger.debug(msg)
                    repo_content_units.update({'_id': rcu['_id']},
                                              {'$set': {'unit_id': conflicting_unit['_id']}})
                except errors.DuplicateKeyError:
                    # We will delete this RepoContentUnit since the sha1 RPM is already in the
                    # repository.
                    msg = _('Removing %(type)s %(old_id)s from repo %(repo_id)s since it conflicts '
                            'with %(conflicting)s.')
                    msg = msg % {'repo_id': rcu['repo_id'], 'type': unit_type,
                                 'conflicting': conflicting_unit['_id'], 'old_id': unit['_id']}
                    _logger.debug(msg)
                    repo_content_units.remove({'_id': rcu['_id']})
                    # In this case, we now need to decrement the repository's "content_unit_counts"
                    # for this unit_type by one, since we removed a unit from a repository.
                    repos.update(
                        {'id': rcu['repo_id']},
                        {'$inc': {'content_unit_counts.%s' % unit_type: -1}})
            # Now that we have removed or altered all references to the "sha" Unit, we need to
            # remove it since it is a duplicate.
            unit_collection.remove({'_id': unit['_id']})


def _migrate_yum_metadata_files():
    """
    Migrate each YumMetadataFile to use the new sanitized checksum_type. This is mostly similar to
    _migrate_rpmlike_units, except that the checksum type field name is checksum_type instead of
    checksumtype, and there can't be any collisions since the checksum type isn't part of this
    unit's unit_key. This means we don't have to worry about the repo_content_units table.
    """
    collection = connection.get_collection('units_yum_repo_metadata_file')
    for unit in collection.find():
        sanitized_type = verification.sanitize_checksum_type(unit['checksum_type'])
        if sanitized_type != unit['checksum_type']:
            collection.update({'_id': unit['_id']},
                              {'$set': {'checksum_type': sanitized_type}})
