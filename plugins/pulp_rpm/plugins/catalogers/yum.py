# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import shutil

from tempfile import mkdtemp
from urlparse import urljoin

from pulp.plugins.cataloger import Cataloger
from pulp.plugins.util.nectar_config import importer_config_to_nectar_config

from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum.repomd.metadata import MetadataFiles
from pulp_rpm.plugins.importers.yum.repomd import primary
from pulp_rpm.plugins.importers.yum.repomd import packages


TYPE_ID = 'yum'
URL = 'url'


def entry_point():
    """
    The Pulp platform uses this method to load the profiler.
    :return: YumCataloger class and an (empty) config
    :rtype:  tuple
    """
    return YumCataloger, {}


class YumCataloger(Cataloger):

    @classmethod
    def metadata(cls):
        return {
            'id': TYPE_ID,
            'display_name': "Yum Cataloger",
            'types': [models.RPM.TYPE]
        }

    @staticmethod
    def _add_packages(source_id, conduit, base_url, md_files):
        with md_files.get_metadata_file_handle(primary.METADATA_FILE_NAME) as fp:
            _packages = packages.package_list_generator(
                fp, primary.PACKAGE_TAG, primary.process_package_element)
            for model in _packages:
                unit_key = model.unit_key
                url = urljoin(base_url, model.download_path)
                conduit.add_entry(source_id, models.RPM.TYPE, unit_key, url)

    def refresh(self, source_id, conduit, config):
        conduit.purge(source_id)
        url = config[URL]
        dst_dir = mkdtemp()
        try:
            nectar_config = importer_config_to_nectar_config(config)
            md_files = MetadataFiles(url, dst_dir, nectar_config)
            md_files.download_repomd()
            md_files.parse_repomd()
            md_files.download_metadata_files()
            self._add_packages(source_id, conduit, url, md_files)
        finally:
            shutil.rmtree(dst_dir)