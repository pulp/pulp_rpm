import os

from pulp.plugins.rsync.publish import Publisher, RSyncPublishStep, UpdateLastPredistDateStep
from pulp.plugins.util.publish_step import RSyncFastForwardUnitPublishStep
from pulp.server.db.model import Distributor
from pulp.server.exceptions import PulpCodedException

from pulp_rpm.common import ids
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.distributors.yum import configuration as yum_config
from pulp_rpm.plugins import error_codes


class RPMRsyncPublisher(Publisher):

    REPO_CONTENT_TYPES = [ids.TYPE_ID_RPM, ids.TYPE_ID_DRPM, ids.TYPE_ID_SRPM]

    REPO_CONTENT_MODELS = [models.RPM, models.SRPM, models.DRPM]

    UNIT_FIELDS = ["_storage_path", "filename"]

    def _get_predistributor(self):
        """
        Returns the distributor that is configured as predistributor.
        """
        predistributor = self.get_config().flatten().get("predistributor_id", None)
        if predistributor:
            return Distributor.objects.get_or_404(repo_id=self.repo.id,
                                                  distributor_id=predistributor)
        else:
            raise PulpCodedException(error_code=error_codes.RPM1010)

    def _get_root_publish_dir(self):
        """
        Returns the publish directory path for the predistributor

        :return: path to the publish directory of the predistirbutor
        :rtype: str
        """
        if self.predistributor["config"].get("https", False):
            return yum_config.get_https_publish_dir(self.get_config())
        else:
            return yum_config.get_http_publish_dir(self.get_config())

    def _add_necesary_steps(self, date_filter=None, config=None):
        """
        This method adds all the steps that are needed to accomplish an RPM rsync publish. This
        includes:

        Unit Query Step - selects units associated with the repo based on the date_filter and
                          creates relative symlinks
        Rsync Step (origin) - rsyncs units discovered in previous step to the remote server
        Rsync Step (repodata) - rsyncs repodata from master publish directory to remote server
        Rsync Step (content) - rsyncs symlinks from working directory to remote server

        :param date_filter:  Q object with start and/or end dates, or None if start and end dates
                             are not provided
        :type date_filter:  mongoengine.Q or types.NoneType
        :param config: distributor configuration
        :type config: pulp.plugins.config.PluginCallConfiguration
        :return: None
        """
        remote_repo_path = yum_config.get_repo_relative_path(self.repo.repo_obj,
                                                             self.predistributor.config)

        # Find all the units associated with repo before last publish with predistributor
        unit_types = ', '.join(RPMRsyncPublisher.REPO_CONTENT_TYPES)
        gen_step = RSyncFastForwardUnitPublishStep("Unit query step (%s)" % unit_types,
                                                   RPMRsyncPublisher.REPO_CONTENT_MODELS,
                                                   repo=self.repo,
                                                   repo_content_unit_q=date_filter,
                                                   remote_repo_path=remote_repo_path,
                                                   published_unit_path=[],
                                                   unit_fields=RPMRsyncPublisher.UNIT_FIELDS)
        self.add_child(gen_step)

        dest_content_units_dir = self.get_units_directory_dest_path()
        src_content_units_dir = self.get_units_src_path()

        # Rsync content units
        self.add_child(RSyncPublishStep("Rsync step (origin)", self.content_unit_file_list,
                                        src_content_units_dir, dest_content_units_dir,
                                        config=config, exclude=[".*", "repodata.old"]))

        # Stop here if distributor is only supposed to publish actual content
        if self.get_config().flatten().get("content_units_only"):
            return

        master_dir = self.get_master_directory()

        # Rsync symlinks to the remote server
        self.add_child(RSyncPublishStep("Rsync step (content)",
                                        self.symlink_list, self.symlink_src,
                                        remote_repo_path,
                                        config=config, links=True, exclude=["repodata"],
                                        delete=self.config.get("delete")))

        repodata_file_list = os.listdir(os.path.join(master_dir, 'repodata'))

        # Only rsync repodata if distributor is configured to do so
        if not self.get_config().get('skip_repodata'):
            self.add_child(RSyncPublishStep("Rsync step (repodata)",
                                            repodata_file_list,
                                            "%s/" % os.path.join(master_dir, 'repodata'),
                                            "%s/" % os.path.join(remote_repo_path, 'repodata'),
                                            exclude=[".*", "repodata.old"],
                                            config=config, links=True,
                                            delete=self.config.get("delete")))

        if self.predistributor:
            self.add_child(UpdateLastPredistDateStep(self.distributor,
                                                     self.predistributor["last_publish"]))
