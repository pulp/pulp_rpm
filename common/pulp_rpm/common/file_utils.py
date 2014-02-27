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

import hashlib

CHECKSUM_CHUNK_SIZE = 32 * 1024 * 1024


def calculate_checksum(file_handle):
    """
    Return the sha256 checksum of the given file-like object.

    :param file_handle: A handle to an open file-like object
    :type  file_handle: file-like object
    :return:            The file's checksum
    :rtype:             string
    """
    file_handle.seek(0)
    hasher = hashlib.sha256()
    bits = file_handle.read(CHECKSUM_CHUNK_SIZE)
    while bits:
        hasher.update(bits)
        bits = file_handle.read(CHECKSUM_CHUNK_SIZE)
    return hasher.hexdigest()


def calculate_size(file_handle):
    """
    Return the size of the given file-like object in Bytes.

    :param file_handle: A handle to an open file-like object
    :type  file_handle: file-like object
    :return:            The file's size, in Bytes
    :rtype:             int
    """
    # Calculate the size by seeking to the end to find the file size with tell()
    file_handle.seek(0, 2)
    size = file_handle.tell()
    return size