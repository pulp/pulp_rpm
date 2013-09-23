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

from pulp_rpm.common import constants, ids
from pulp_rpm.repo_auth import protected_repo_utils, repo_cert_utils
from pulp_rpm.yum_plugin import comps_util, util, metadata, updateinfo

# -- global constants ----------------------------------------------------------

_LOG = util.getLogger(__name__)


# -- distributor ---------------------------------------------------------------

class YumDistributor(Distributor):

    def __init__(self):
        super(YumDistributor, self).__init__()
        self.canceled = False

    @classmethod
    def metadata(cls):
        return {'id': ids.TYPE_ID_DISTRIBUTOR_YUM,
                'display_name': 'Yum Distributor',
                'types': [ids.TYPE_ID_RPM, ids.TYPE_ID_SRPM, ids.TYPE_ID_DRPM, ids.TYPE_ID_ERRATA,
                          ids.TYPE_ID_DISTRO, ids.TYPE_ID_PKG_CATEGORY, ids.TYPE_ID_PKG_GROUP,
                          ids.TYPE_ID_YUM_REPO_METADATA_FILE]}

    # -- repo lifecycle methods ------------------------------------------------

    def validate_config(self, repo, config, config_conduit):
        raise NotImplementedError()

    def distributor_added(self, repo, config):
        pass

    def distributor_removed(self, repo, config):
        pass

    # -- actions ---------------------------------------------------------------

    def publish_repo(self, repo, publish_conduit, config):
        raise NotImplementedError()

    def cancel_publish_repo(self, call_request, call_report):
        raise NotImplementedError()

    def create_consumer_payload(self, repo, config, binding_config):
        return {}

