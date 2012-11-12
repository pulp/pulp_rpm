# -*- coding: utf-8 -*-
# Migration script to set custom metadata on repo scratchpad
#
# Copyright © 2010-2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

import os
import gzip
import logging

from pulp.server.managers import factory
from pulp.server.managers.repo._common import importer_working_dir
from pulp_rpm.yum_plugin import util

_log = logging.getLogger('pulp')

def preserve_custom_metadata_on_repo_scratchpad():
    """
     Lookups all the yum based repos in pulp; grabs any custom metadata
     and set the the data on repo scratchpad.
    """
    factory.initialize()
    repos = factory.repo_query_manager().find_with_importer_type("yum_importer")
    if not repos:
        _log.debug("No repos found to perform db migrate")
        return
    repo_ids = [repo['id'] for repo in repos]
    for repo_id in repo_ids:
        _log.debug("Processing repo %s" % repo_id)
        repo_scratchpad = factory.repo_manager().get_repo_scratchpad(repo_id)
        if repo_scratchpad.has_key("repodata") and repo_scratchpad["repodata"]:
            # repo scratchpad already has repodata, skip migration
            _log.debug("repo [%s] scratchpad already has repodata, skip migration" % repo_id)
            continue
        repo_working_dir = importer_working_dir('yum_importer', repo_id)
        importer_repodata_dir = os.path.join(repo_working_dir, repo_id, "repodata")
        repomd_xml_path = os.path.join(importer_repodata_dir, "repomd.xml")
        if not os.path.exists(repomd_xml_path):
            # repodata doesn't exist on filesystem cannot lookup custom data, continue to next
            continue
        ftypes = util.get_repomd_filetypes(repomd_xml_path)
        base_ftypes = ['primary', 'primary_db', 'filelists_db', 'filelists', 'other', 'other_db',
                       'group', 'group_gz', 'updateinfo', 'updateinfo_db']
        for ftype in ftypes:
            if ftype in base_ftypes:
                # no need to process these again
                continue
            filetype_path = os.path.join(importer_repodata_dir,
                os.path.basename(util.get_repomd_filetype_path(repomd_xml_path, ftype)))
            if filetype_path.endswith('.gz'):
                # if file is gzipped, decompress
                data = gzip.open(filetype_path).read().decode("utf-8", "replace")
            else:
                data = open(filetype_path).read().decode("utf-8", "replace")
            repo_scratchpad["repodata"].update({ftype : data})
        # set the custom metadata on scratchpad
        factory.repo_manager().set_repo_scratchpad(repo_id, repo_scratchpad)
        _log.info("Updated repo [%s] scratchpad with new custom repodata" % repo_id)

def migrate(*args, **kwargs):
    preserve_custom_metadata_on_repo_scratchpad()