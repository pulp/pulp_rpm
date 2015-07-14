from gettext import gettext as _

from pulp.plugins.importer import Importer
from pulp.common.config import read_json_config
from pulp.server.db import model as platform_models

from pulp_rpm.common import ids
from pulp_rpm.plugins.importers.yum import sync, associate, upload, config_validate


# The platform currently doesn't support automatic loading of conf files when the plugin
# uses entry points. The current thinking is that the conf files will be named the same as
# the plugin and put in a conf.d type of location. For now, this implementation will assume
# that's the final solution and the plugin will attempt to load the file itself in the
# entry_point method.
CONF_FILENAME = 'server/plugins.conf.d/%s.json' % ids.TYPE_ID_IMPORTER_YUM


def entry_point():
    """
    Entry point that pulp platform uses to load the importer
    :return: importer class and its config
    :rtype:  Importer, {}
    """
    plugin_config = read_json_config(CONF_FILENAME)
    return YumImporter, plugin_config


class YumImporter(Importer):
    @classmethod
    def metadata(cls):
        return {
            'id': ids.TYPE_ID_IMPORTER_YUM,
            'display_name': _('Yum Importer'),
            'types': [
                ids.TYPE_ID_DISTRO, ids.TYPE_ID_DRPM, ids.TYPE_ID_ERRATA,
                ids.TYPE_ID_PKG_GROUP, ids.TYPE_ID_PKG_CATEGORY, ids.TYPE_ID_RPM,
                ids.TYPE_ID_SRPM, ids.TYPE_ID_YUM_REPO_METADATA_FILE, ids.TYPE_ID_PKG_ENVIRONMENT
            ]
        }

    def validate_config(self, repo, config):
        return config_validate.validate(config)

    def import_units(self, source_transfer_repo, dest_transfer_repo, import_conduit, config, units=None):
        source_repo = platform_models.Repository.objects.get(repo_id=source_transfer_repo.id)
        dest_repo = platform_models.Repository.objects.get(repo_id=dest_transfer_repo.id)

        return associate.associate(source_repo, dest_repo, import_conduit, config, units)

    def upload_unit(self, transfer_repo, type_id, unit_key, metadata, file_path, conduit, config):
        repo = platform_models.Repository.objects.get(repo_id=transfer_repo.id)
        repo.repo_id = transfer_repo.id
        conduit.repo = repo
        return upload.upload(repo, type_id, unit_key, metadata, file_path, conduit, config)

    def sync_repo(self, transfer_repo, sync_conduit, call_config):
        """
        :param transfer_repo: metadata describing the repository
        :type  transfer_repo: pulp.plugins.model.Repository

        :param sync_conduit: provides access to relevant Pulp functionality
        :type  sync_conduit: pulp.plugins.conduits.repo_sync.RepoSyncConduit

        :param call_config: plugin configuration
        :type  call_config: pulp.plugins.config.PluginCallConfiguration

        :return: report of the details of the sync
        :rtype:  pulp.plugins.model.SyncReport
        """
        repo = platform_models.Repository.objects.get(repo_id=transfer_repo.id)
        sync_conduit.repo = repo
        self._current_sync = sync.RepoSync(repo, sync_conduit, call_config)
        report = self._current_sync.run()
        self._current_sync.finalize()
        return report

    def cancel_sync_repo(self):
        """
        Cancel a currently running repository synchronization operation.
        """
        self._current_sync.cancel()
        self._current_sync.finalize()
