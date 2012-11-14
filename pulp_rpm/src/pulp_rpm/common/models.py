# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version 
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

class ISO(object):
    def __init__(self, name, size, checksum):
        self.name = name
        self.size = size
        self.checksum = checksum


class ISORepositoryMetadata(object):
    def __init__(self, metadata_csv=None):
        self.isos = []
        if metadata_csv:
            self.update_from_csv(metadata_csv)

    def update_from_csv(self, metadata_csv):
        metadata_reader = csv.Reader(metadata_csv)
        for row in metadata_reader:
            self.isos.append(ISO(name=row[0], size=row[1], checksum=row[2]))
