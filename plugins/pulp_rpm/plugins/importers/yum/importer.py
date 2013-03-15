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

from gettext import gettext as _
import gzip
import shutil
import tempfile

from pulp.plugins.importer import Importer

from pulp_rpm.common import ids, models, constants
from pulp_rpm.plugins.importers.download import metadata, primary, packages
from pulp_rpm.plugins.importers.yum.listener import Listener


class YumImporter(Importer):
    def metadata(cls):
        return {
            'id': ids.TYPE_ID_IMPORTER_YUM,
            'display_name': _('Yum Importer'),
            'types': [
                ids.TYPE_ID_DISTRO, ids.TYPE_ID_DRPM, ids.TYPE_ID_ERRATA,
                ids.TYPE_ID_PKG_GROUP, ids.TYPE_ID_PKG_CATEGORY, ids.TYPE_ID_RPM,
                ids.TYPE_ID_SRPM,
            ]
        }

    def validate_config(self, repo, config, related_repos):
        return True, None

    def upload_unit(self, repo, type_id, unit_key, metadata, file_path, conduit, config):
        rpm = models.RPM(metadata=metadata, **unit_key)
        unit = conduit.init_unit(type_id, rpm.unit_key, rpm.metadata, rpm.relative_path)
        try:
            shutil.copy(file_path, unit.storage_path)
        except IOError:
            # do something sensible here
            raise

        conduit.save_unit(unit)

    def sync_repo(self, repo, sync_conduit, config):
        feed = config[constants.CONFIG_FEED_URL]
        current_units = sync_conduit.get_units()
        event_listener = Listener(sync_conduit)
        tmp_dir = tempfile.mkdtemp()
        try:
            metadata_files = metadata.MetadataFiles(feed, tmp_dir)
            metadata_files.download_remomd()
            metadata_files.parse_remomd()
            #metadata_files.verify_metadata_files()

            primary_file_path = metadata_files.metadata['primary']['local_path']

            if primary_file_path.endswith('.gz'):
                primary_file_handle = gzip.open(primary_file_path, 'r')
            else:
                primary_file_handle = open(primary_file_path, 'r')

            with primary_file_handle:
                package_info_generator = primary.primary_package_list_generator(primary_file_handle)
                units_to_download = self._filtered_unit_generator(package_info_generator, current_units)

                packages_manager = packages.Packages(feed, units_to_download, tmp_dir, event_listener)
                packages_manager.download_packages()

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _filtered_unit_generator(self, units, current_units):
        for unit in units:
            # decide if this unit should be downloaded
            yield unit
