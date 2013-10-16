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

import os
import sys
import traceback

from yum import update_md

from pulp_rpm.plugins.distributors.yum import metadata


def main():
    try:
        update_info_file_path = sys.argv[1]
        output_directory = sys.argv[2]

    except IndexError:
        print 'Usage: %s <update info file path> <output directory>'
        return os.EX_NOINPUT

    update_metadata = update_md.UpdateMetadata()
    update_metadata.add(update_info_file_path)

    with metadata.UpdateinfoXMLFileContext(output_directory) as update_info_file_context:

        try:
            for notice in update_metadata.get_notices():
                update_info_file_context.add_unit_metadata(notice._md)

        except:
            traceback.print_exc(file=sys.stderr)
            return os.EX_SOFTWARE

    return os.EX_OK

# -- main ----------------------------------------------------------------------

if __name__ == '__main__':
    sys.exit(main())
