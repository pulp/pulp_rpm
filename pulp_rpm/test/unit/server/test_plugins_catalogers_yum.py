# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.


from rpm_support_base import PulpRPMTests

from pulp.server.db.model.content import ContentCatalog
from pulp.plugins.conduits.cataloger import CatalogerConduit

from pulp_rpm.plugins.catalogers.yum import YumCataloger, entry_point


class TestYumProfiler(PulpRPMTests):

    def setUp(self):
        PulpRPMTests.setUp(self)
        ContentCatalog.get_collection().remove()

    def tearDown(self):
        PulpRPMTests.tearDown(self)
        ContentCatalog.get_collection().remove()

    def test_entry_point(self):
        plugin, config = entry_point()
        self.assertEqual(plugin, YumCataloger)
        self.assertEqual(config, {})

    def test_packages(self):
        config = {
            'url': 'http://repos.fedorapeople.org/repos/pulp/pulp/beta/2.3/5Server/x86_64/'
        }
        source_id = 'test'
        conduit = CatalogerConduit()
        cataloger = YumCataloger()
        cataloger.refresh(source_id, conduit, config)