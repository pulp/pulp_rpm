from pulp.plugins.rsync.publish import Publisher, RSyncPublishStep, UpdateLastPredistDateStep
from pulp.plugins.util.publish_step import RSyncFastForwardUnitPublishStep
from pulp.server.db.model import Distributor
from pulp.server.exceptions import PulpCodedException

from pulp_rpm.common import constants
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins.distributors.yum.configuration import get_repo_relative_path


class ISORsyncPublisher(Publisher):

    REPO_CONTENT_MODELS = [models.ISO]

    UNIT_FIELDS = ["_storage_path", "name"]

    def _get_predistributor(self):
        """
        Returns the distributor that is configured as predistributor.
        """
        predistributor = self.get_config().flatten().get("predistributor_id", None)
        if predistributor:
            return Distributor.objects.get_or_404(repo_id=self.repo.id,
                                                  distributor_id=predistributor)
        else:
            raise PulpCodedException(error_code=error_codes.RPM1011)

    def _get_root_publish_dir(self):
        """
        Returns the publish directory path for the predistributor.

        :return: absolute path to the master publish directory of predistributor
        :rtype: str
        """
        if self.predistributor["config"].get("serve_http", False):
            return constants.ISO_HTTP_DIR
        else:
            return constants.ISO_HTTPS_DIR

    def _add_necesary_steps(self, date_filter=None, config=None):
        """
        This method adds all the steps that are needed to accomplish an ISO rsync publish. This
        includes:

        Unit Query Step - selects units associated with the repo based on the date_filter and
                          creates relative symlinks
        Rsync Step (content units) - rsyncs units discovered in previous step to the remote server
        Rsync Step (symlinks) - rsyncs symlinks from working directory to remote server
        Rsync Step (PULP_MANIFEST) - rsyncs PULP_MANIFEST to remote server


        :param date_filter:  Q object with start and/or end dates, or None if start and end dates
                             are not provided
        :type date_filter:  mongoengine.Q or types.NoneType
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        remote_repo_path = get_repo_relative_path(self.repo.repo_obj, self.predistributor.config)

        # Find all the units associated with repo before last publish with predistributor
        gen_step = RSyncFastForwardUnitPublishStep("Unit query step (ISO)",
                                                   ISORsyncPublisher.REPO_CONTENT_MODELS,
                                                   repo=self.repo,
                                                   repo_content_unit_q=date_filter,
                                                   remote_repo_path=remote_repo_path,
                                                   published_unit_path=[],
                                                   unit_fields=ISORsyncPublisher.UNIT_FIELDS)
        self.add_child(gen_step)

        dest_content_units_dir = self.get_units_directory_dest_path()
        src_content_units_dir = self.get_units_src_path()

        # Rsync content units
        self.add_child(RSyncPublishStep("Rsync step (content units)", self.content_unit_file_list,
                                        src_content_units_dir, dest_content_units_dir,
                                        config=config, exclude=[]))

        # Stop here if distributor is only supposed to publish actual content
        if self.get_config().flatten().get("content_units_only"):
            return

        # Rsync symlinks to the remote server
        self.add_child(RSyncPublishStep("Rsync step (symlinks)",
                                        self.symlink_list, self.symlink_src,
                                        remote_repo_path,
                                        config=config, links=True, exclude=["PULP_MANIFEST"],
                                        delete=self.config.get("delete")))

        predistributor_master_dir = self.get_master_directory()

        # Rsync PULP_MANIFEST
        self.add_child(RSyncPublishStep("Rsync step (PULP_MANIFEST)",
                                        ['PULP_MANIFEST'], predistributor_master_dir,
                                        remote_repo_path,
                                        config=config))

        if self.predistributor:
            self.add_child(UpdateLastPredistDateStep(self.distributor,
                                                     self.predistributor["last_publish"]))
