import logging

from gettext import gettext as _

from pulp.server.db.connection import get_collection
from pulp.server.db.migrations.lib import utils

_LOGGER = logging.getLogger('pulp_rpm.plugins.migrations.0046')

units_rpm_collection = get_collection('units_rpm')
units_modulemd_collection = get_collection('units_modulemd')

NEW_FIELD = 'is_modular'


def nevra(name):
    """Parse NEVRA.

    inspired by:
    https://github.com/rpm-software-management/hawkey/blob/d61bf52871fcc8e41c92921c8cd92abaa4dfaed5/src/util.c#L157. # NOQA
    We don't use hawkey because it is not available on all platforms we support.

    :param name: NEVRA (jay-3:3.10-4.fc3.x86_64)
    :type  name: str

    :return: parsed NEVRA (name, epoch, version, release, architecture)
                           str    int     str      str         str
    :rtype: tuple
    """
    if name.count(".") < 1:
        msg = _("failed to parse nevra '%s' not a valid nevra") % name
        _LOGGER.exception(msg)
        raise ValueError(msg)

    arch_dot_pos = name.rfind(".")
    arch = name[arch_dot_pos + 1:]

    return nevr(name[:arch_dot_pos]) + (arch, )


def nevr(name):
    """
    Parse NEVR.

    inspired by:
    https://github.com/rpm-software-management/hawkey/blob/d61bf52871fcc8e41c92921c8cd92abaa4dfaed5/src/util.c#L157. # NOQA

    :param name: NEVR "jay-test-3:3.10-4.fc3"
    :type  name: str

    :return: parsed NEVR (name, epoch, version, release)
                          str    int     str      str
    :rtype: tuple
    """
    if name.count("-") < 2:  # release or name is missing
        msg = _("failed to parse nevr '%s' not a valid nevr") % name
        _LOGGER.exception(msg)
        raise ValueError(msg)

    release_dash_pos = name.rfind("-")
    release = name[release_dash_pos + 1:]
    name_epoch_version = name[:release_dash_pos]
    name_dash_pos = name_epoch_version.rfind("-")
    package_name = name_epoch_version[:name_dash_pos]

    epoch_version = name_epoch_version[name_dash_pos + 1:].split(":")
    if len(epoch_version) == 1:
        epoch = 0
        version = epoch_version[0]
    elif len(epoch_version) == 2:
        epoch = int(epoch_version[0])
        version = epoch_version[1]
    else:
        # more than one ':'
        msg = _("failed to parse nevr '%s' not a valid nevr") % name
        _LOGGER.exception(msg)
        raise ValueError(msg)

    return package_name, epoch, version, release


def migrate_modulemd_artifacts(modulemd):
    """
    Set is_modular flag to True for modulemd's artifacts.

    :param modulemd: module for which artifacts should be updated
    :type  modulemd: pulp_rpm.plugins.db.models.Modulemd
    """
    delta = {'is_modular': True}
    for artifact in modulemd.get('artifacts'):
        pkg_nevra = nevra(artifact)
        search_criteria = {'name': pkg_nevra[0],
                           'epoch': unicode(pkg_nevra[1]),
                           'version': pkg_nevra[2],
                           'release': pkg_nevra[3],
                           'arch': pkg_nevra[4],
                           NEW_FIELD: {'$exists': False}}

        for rpm in units_rpm_collection.find(search_criteria, ['_id']):
            units_rpm_collection.update_one({'_id': rpm['_id']}, {'$set': delta})


def migrate(*args, **kwargs):
    """
    Add `is_modular` field to RPM collection.

    Set this field appropriately for RPM collection based on available info in modulemd units.

    :param args:   unused
    :type  args:   list
    :param kwargs: unused
    :type  kwargs: dict
    """
    total_modulemd_units = units_modulemd_collection.count()

    with utils.MigrationProgressLog('Modulemd artifacts', total_modulemd_units) as migration_log:
        for modulemd in units_modulemd_collection.find({}, ['artifacts']).batch_size(100):
            migrate_modulemd_artifacts(modulemd)
            migration_log.progress()

    total_rpm_units = units_rpm_collection.count({NEW_FIELD: {'$exists': False}})

    if total_rpm_units:
        with utils.MigrationProgressLog('RPM', total_rpm_units) as migration_log:
            units_rpm_collection.update_many({NEW_FIELD: {'$exists': False}},
                                             {'$set': {NEW_FIELD: False}})
            migration_log.progress(migrated_units=total_rpm_units)
