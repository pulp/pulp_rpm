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

import logging
import shutil

from pulp.common.download.listener import DownloadEventListener, AggregatingEventListener


_LOGGER = logging.getLogger(__name__)


class DistroFileListener(AggregatingEventListener):
    def __init__(self, progress_report, progress_callback):
        super(DistroFileListener, self).__init__()
        self.progress_report = progress_report
        self.progress_callback = progress_callback

    def download_succeeded(self, report):
        self._decrement()
        super(DistroFileListener, self).download_succeeded(report)

    def download_failed(self, report):
        self._decrement()
        super(DistroFileListener, self).download_succeeded(report)

    def _decrement(self):
        self.progress_report['items_left'] -= 1
        self.progress_callback()


class ContentListener(DownloadEventListener):
    def __init__(self, sync_conduit, progress_report):
        super(ContentListener, self).__init__()
        self.sync_conduit = sync_conduit
        self.progress_report = progress_report

    def download_succeeded(self, report):
        """

        :param report:
        :type  report: pulp.common.download.report.DownloadReport
        :return:
        """
        model = report.data
        # init unit, which is idempotent
        unit = self.sync_conduit.init_unit(model.TYPE, model.unit_key, model.metadata, model.relative_path)
        # move to final location
        shutil.move(report.destination, unit.storage_path)
        # save unit
        self.sync_conduit.save_unit(unit)
        self.progress_report['content'].success(model)
        self.sync_conduit.set_progress(self.progress_report)

    def download_failed(self, report):
        """

        :param report:
        :type  report: pulp.common.download.report.DownloadReport
        :return:
        """
        model = report.data
        self.progress_report['content'].failure(model, report.error_report)
        self.sync_conduit.set_progress(self.progress_report)

