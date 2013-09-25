# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

from pulp.plugins.distributor import Distributor
from pulp.server import config as pulp_config
from pulp.server.db.model.criteria import UnitAssociationCriteria

from pulp_rpm.common import constants
from pulp_rpm.common.ids import (
    TYPE_ID_DISTRIBUTOR_YUM, TYPE_ID_DISTRO, TYPE_ID_DRPM, TYPE_ID_ERRATA,
    TYPE_ID_PKG_CATEGORY, TYPE_ID_PKG_GROUP, TYPE_ID_RPM, TYPE_ID_SRPM,
    TYPE_ID_YUM_REPO_METADATA_FILE)
from pulp_rpm.repo_auth import protected_repo_utils, repo_cert_utils
from pulp_rpm.yum_plugin import comps_util, util, metadata, updateinfo

from . import configuration, publish

# -- global constants ----------------------------------------------------------

_LOG = util.getLogger(__name__)

DISTRIBUTOR_DISPLAY_NAME = 'Yum Distributor'

# -- distributor ---------------------------------------------------------------

class YumHTTPDistributor(Distributor):

    def __init__(self):
        super(YumHTTPDistributor, self).__init__()

        self.canceled = False
        self._publisher = None

    @classmethod
    def metadata(cls):
        return {'id': TYPE_ID_DISTRIBUTOR_YUM,
                'display_name': DISTRIBUTOR_DISPLAY_NAME,
                'types': [TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                          TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY, TYPE_ID_DISTRO,
                          TYPE_ID_YUM_REPO_METADATA_FILE]}

    # -- repo lifecycle methods ------------------------------------------------

    def validate_config(self, repo, config, config_conduit):
        return configuration.validate_config(repo, config, config_conduit)

    def distributor_added(self, repo, config):
        pass

    def distributor_removed(self, repo, config):
        pass

    # -- actions ---------------------------------------------------------------

    def publish_repo(self, repo, publish_conduit, config):
        self._publisher = publish.Publisher(repo, publish_conduit, config)
        self._publisher.publish()

    def cancel_publish_repo(self, call_request, call_report):
        self.canceled = True
        if self._publisher is not None:
            self._publisher.cancel()

    def create_consumer_payload(self, repo, config, binding_config):
        return {}

    # -- action helper methods -------------------------------------------------

