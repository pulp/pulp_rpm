import logging
import os
import shutil

from pulp.common import config as config_utils
from pulp.common.plugins import importer_constants
from pulp.plugins.conduits.mixins import UnitAssociationCriteria
from pulp.plugins.importer import Importer

from pulp_rpm.common import constants, ids
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.iso import configuration, sync


logger = logging.getLogger(__name__)


# The leading '/etc/pulp/' will be added by the read_json_config method.
CONF_FILENAME = 'server/plugins.conf.d/%s.json' % ids.TYPE_ID_IMPORTER_ISO


def entry_point():
    """
    This method allows us to announce this importer to the Pulp Platform.

    :return: importer class as its config
    :rtype:  tuple
    """
    return ISOImporter, config_utils.read_json_config(CONF_FILENAME)


class ISOImporter(Importer):
    """
    All methods that are missing docstrings are documented in the Importer superclass.
    """

    def cancel_sync_repo(self):
        """
        Cancel a running repository synchronization operation.
        """
        self.iso_sync.cancel_sync()

    def import_units(self, source_repo, dest_repo, import_conduit, config, units=None):
        """
        Import content units into the given repository. This method will be
        called in a number of different situations:
         * A user is attempting to copy a content unit from one repository
           into the repository that uses this importer
         * A user is attempting to add an orphaned unit into a repository.

        This call has two options for handling the requested units:
         * Associate the given units with the destination repository. This will
           link the repository with the existing unit directly; changes to the
           unit will be reflected in all repositories that reference it.
         * Create a new unit and save it to the repository. This would act as
           a deep copy of sorts, creating a unique unit in the database. Keep
           in mind that the unit key must change in order for the unit to
           be considered different than the supplied one.

        The APIs for both approaches are similar to those in the sync conduit.
        In the case of a simple association, the init_unit step can be skipped
        and save_unit simply called on each specified unit.

        The units argument is optional. If None, all units in the source
        repository should be imported. The conduit is used to query for those
        units. If specified, only the units indicated should be imported (this
        is the case where the caller passed a filter to Pulp).

        :param source_repo: metadata describing the repository containing the
               units to import
        :type  source_repo: pulp.plugins.model.Repository

        :param dest_repo: metadata describing the repository to import units
               into
        :type  dest_repo: pulp.plugins.model.Repository

        :param import_conduit: provides access to relevant Pulp functionality
        :type  import_conduit: pulp.plugins.conduits.unit_import.ImportUnitConduit

        :param config: plugin configuration
        :type  config: pulp.plugins.config.PluginCallConfiguration

        :param units: optional list of pre-filtered units to import
        :type  units: list of pulp.plugins.model.Unit

        :return: list of Unit instances that were saved to the destination repository
        :rtype:  list
        """
        if units is None:
            criteria = UnitAssociationCriteria(type_ids=[ids.TYPE_ID_ISO])
            units = import_conduit.get_source_units(criteria=criteria)

        for u in units:
            import_conduit.associate_unit(u)

        return units

    @classmethod
    def metadata(cls):
        return {
            'id': ids.TYPE_ID_IMPORTER_ISO,
            'display_name': 'ISO Importer',
            'types': [ids.TYPE_ID_ISO]
        }

    def sync_repo(self, repo, sync_conduit, config):
        if config.get(importer_constants.KEY_FEED) is None:
            raise ValueError('Repository without feed cannot be synchronized')
        self.iso_sync = sync.ISOSyncRun(sync_conduit, config)
        report = self.iso_sync.perform_sync()
        self.iso_sync = None
        return report

    def upload_unit(self, repo, type_id, unit_key, metadata, file_path, conduit, config):
        """
        See super(self.__class__, self).upload_unit() for the docblock explaining this method. In
        short, it handles ISO uploads.
        """
        iso = models.ISO(unit_key['name'], unit_key['size'], unit_key['checksum'])
        iso.init_unit(conduit)

        shutil.move(file_path, iso.storage_path)
        validate = config.get_boolean(importer_constants.KEY_VALIDATE)
        validate = validate if validate is not None else constants.CONFIG_VALIDATE_DEFAULT
        try:
            # Let's validate the ISO. This will raise a
            # ValueError if the ISO does not validate correctly.
            iso.validate(full_validation=validate)
        except ValueError, e:
            # If validation raises a ValueError, we should delete the file and raise
            os.remove(iso.storage_path)
            return {'success_flag': False, 'summary': e.message, 'details': None}

        iso.save_unit(conduit)
        return {'success_flag': True, 'summary': None, 'details': None}

    def validate_config(self, repo, config):
        return configuration.validate(config)
