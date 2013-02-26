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
# You should have received a copy of GPLv2 along with this software; if not,
# see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

# This script is to test the yum repo download package for the importer

import gzip
import resource
import sys
from datetime import datetime

from pulp_rpm.plugins.importers.download import metadata
from pulp_rpm.plugins.importers.download import packages
from pulp_rpm.plugins.importers.download import primary


EPEL_REPO_URL = 'http://epel.mirrors.arminco.com/6/x86_64/'
MMCCUNE_MEDIUM_REPO_URL = 'http://mmccune.fedorapeople.org/repos/medium/'
PULP_DEMO_REPO_URL = 'http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/pulp_unittest/'


def get_repo_url():
    last_arg = sys.argv[-1]
    if last_arg.startswith('http'):
        return last_arg
    return MMCCUNE_MEDIUM_REPO_URL


def main(repo_url):
    start_time = datetime.now()
    start_rusage = resource.getrusage(resource.RUSAGE_SELF)

    metadata_files = metadata.MetadataFiles(repo_url)
    metadata_files.download_repomd()

    repomd_download_time = datetime.now()
    repomd_download_rusage = resource.getrusage(resource.RUSAGE_SELF)

    metadata_files.parse_repomd()

    repomd_parse_time = datetime.now()
    repomd_parse_rusage = resource.getrusage(resource.RUSAGE_SELF)

    metadata_files.download_metadata_files()

    metadata_files_download_time = datetime.now()
    metadata_files_download_rusage = resource.getrusage(resource.RUSAGE_SELF)

    #metadata_files.verify_metadata_files()

    metadata_files_verify_time = datetime.now()
    metadata_files_verify_rusage = resource.getrusage(resource.RUSAGE_SELF)

    primary_file_path = metadata_files.metadata['primary']['local_path']

    if primary_file_path.endswith('.gz'):
        primary_file_handle = gzip.open(primary_file_path, 'r')
    else:
        primary_file_handle = open(primary_file_path, 'r')

    package_info_generator = primary.primary_package_list_generator(primary_file_handle)

    packages_manager = packages.Packages(repo_url, package_info_generator)
    packages_manager.download_packages()

    primary_parse_and_package_download_time = datetime.now()
    primary_parse_and_package_download_rusage = resource.getrusage(resource.RUSAGE_SELF)

    print 'repomd download time: %s' % str(repomd_download_time - start_time)
    print 'repomd parse time: %s' % str(repomd_parse_time - repomd_download_time)
    print 'metadata files download time: %s' % str(metadata_files_download_time - repomd_parse_time)
    #print 'metadata files verification time: %s' % str(metadata_files_verify_time - metadata_files_download_time)
    print 'combined primary parse and package download time: %s' % str(primary_parse_and_package_download_time - metadata_files_verify_time)

    print ''

    def reduce_memory_usage(reduce_func, rusage_list):
        return reduce_func(u.ru_idrss + u.ru_ixrss for u in rusage_list)

    rusage_list = (start_rusage, repomd_download_rusage, repomd_parse_rusage,
                   metadata_files_download_rusage, metadata_files_verify_rusage,
                   primary_parse_and_package_download_rusage)

    print 'minimum memory usage: %s' % str(reduce_memory_usage(min, rusage_list))
    print 'maximum memory usage: %s' % str(reduce_memory_usage(max, rusage_list))

    print ''

    print 'metadata files directory: %s' % metadata_files.dst_dir
    print 'packages directory: %s' % packages_manager.dst_dir

# ------------------------------------------------------------------------------

if __name__ == '__main__':
    repo_url = get_repo_url()
    main(repo_url)

