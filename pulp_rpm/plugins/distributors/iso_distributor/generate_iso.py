# -*- coding: utf-8 -*-
#
# Copyright © 2011 Red Hat, Inc.
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
import commands
import datetime
import tempfile
from stat import ST_SIZE

import export_utils
from pulp_rpm.common import constants
from pulp_rpm.yum_plugin.util import getLogger
log = getLogger(__name__)

# Define the size (in megabytes) of a DVD sized ISO
DVD_ISO_SIZE = 4380

MKISOFS_COMMAND_TEMPLATE = "mkisofs -r -D -graft-points -path-list %s -o %s"


def create_iso(target_dir, output_dir, prefix, image_size=DVD_ISO_SIZE, progress_callback=None):
    """
    Run the export process.

    :param target_dir:          The directory to be written to ISO images
    :type  target_dir:          str
    :param output_dir:          destination directory where the ISO images are written
    :type  output_dir:          str
    :param prefix:              prefix for the ISO file names; usually includes a repo id
    :type  prefix:              str
    :param image_size:          The maximum size of the image in bytes. Defaults to a dvd sized image.
    :type  image_size:          int
    :param progress_callback:   callback to report progress info to publish_conduit. This is expected to
                                    take the following parameters: a string to use as the key in a
                                    dictionary, and the second parameter is assigned to it.
    :type  progress_callback:   function
    """
    # Validate the configuration
    image_size = _parse_image_size(image_size)

    # record start time
    start_time = datetime.datetime.now()

    # get size and file list of the target directory
    file_list, total_dir_size = _get_dir_file_list_and_size(target_dir)

    # image_list is a list of the images to write. Each item in the list is a list of file paths.
    image_list = _compute_image_files(file_list, image_size)
    image_count = len(image_list)

    # Update the progress report
    iso_progress_status = export_utils.init_progress_report(image_count)
    set_progress("isos", iso_progress_status, progress_callback)

    for i in range(image_count):
        name = "%s-%s-%02d.iso" % (prefix, start_time.strftime("%Y-%m-%dT%H.%M"), i + 1)
        _make_iso(image_list[i], target_dir, output_dir, name)

        # Update the progress report
        iso_progress_status[constants.PROGRESS_ITEMS_LEFT_KEY] -= 1
        iso_progress_status[constants.PROGRESS_NUM_SUCCESS_KEY] += 1
        set_progress("isos", iso_progress_status, progress_callback)

    iso_progress_status["state"] = constants.STATE_COMPLETE
    set_progress("isos", iso_progress_status, progress_callback)


def _make_iso(file_list, target_dir, output_dir, filename):
    """
    Helper method to make an ISO image. This method could result in an OSError or IOError if something
    went wrong when generating the pathspec_file.

    :param file_list:   List of files to add to the ISO image. These should be absolute paths to the files
    :type  file_list:   list
    :param target_dir:  The full path to the root directory tree to be wrapped in an ISO
    :type  target_dir:  str
    :param output_dir:  The full path to the output directory for the ISO image
    :type  output_dir:  str
    :param filename:    The filename to use for the ISO image. This should be relative to the output
                            directory.
    :type  filename:    str
    """
    file_path = os.path.join(output_dir, filename)

    # If the output directory doesn't exist, make it
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    # Create a pathspec file using the files in this image.
    pathspec_file = _get_pathspec_file(file_list, target_dir)

    # Call mkisofs to create the ISO, then clean up the temporary pathspec file
    status, out = commands.getstatusoutput(MKISOFS_COMMAND_TEMPLATE % (pathspec_file, file_path))
    os.unlink(pathspec_file)

    if status != 0:
        log.error("Error creating iso %s; status code: %d; output: %s" % (file_path, status, out))
    else:
        log.info('Successfully created iso %s' % file_path)


def _parse_image_size(image_size):
    """
    Parses the image_size value and raises the appropriate exception if necessary

    :param image_size: The ISO image size in megabytes
    :type  image_size: int or str

    :return: The ISO image size in bytes
    :rtype:  int

    :raise: ValueError if image_size cast to an int is smaller than or equal to 0
    """
    if image_size is None:
        image_size = DVD_ISO_SIZE

    image_size = int(image_size)
    if 0 >= image_size:
        raise ValueError('Image size must be an integer greater than 0')
    return image_size * 1024 * 1024


def _compute_image_files(file_list, max_image_size):
    """
    Compute file lists to be written to each media image by shoving files into an image until
    image_size is exceeded.

    :param file_list:       A list of tuples, where each tuple is (file_path, file_size), usually the
                                output of get_dir_file_list_and_size
    :type  file_list:       [(str, int)]
    :param max_image_size:  The maximum size of image in bytes
    :type  max_image_size:  int

    :return: list of images, which are themselves a list of file paths
    :rtype: list of list of str
    """
    images = []

    # While we have files in the list, create images
    while len(file_list) > 0:
        image = []
        image_size = 0
        # Keep track of the last file written so we can trim the list
        last_file_written = None

        for file_path, file_size in file_list:
            # An edge case, but if the file is too big to fit on a single ISO, we should stop
            if file_size > max_image_size:
                raise ValueError('The maximum ISO size is not large enough to contain %s' % file_path)

            if image_size + file_size > max_image_size:
                # If adding this file exceeds image size, break out of the for loop
                break

            # Append the file path to the image and update the size of this image
            image.append(file_path)
            image_size += file_size
            last_file_written = (file_path, file_size)

        # Trim the list to the last item written plus 1, then add the image and start again
        file_list = file_list[file_list.index(last_file_written) + 1:]
        images.append(image)

    return images


def set_progress(type_id, progress_status, progress_callback):
    """
    This just checks that progress_callback is not None before calling it

    :param type_id:             The type id to use with the progress callback
    :type  type_id:             str
    :param progress_status:     The progress status to use with the progress callback
    :type  progress_status:     dict
    :param progress_callback:   The progress callback function to use
    :type  progress_callback:   function
    """
    if progress_callback:
        progress_callback(type_id, progress_status)


def _get_grafts(img_file_paths, target_dir):
    """
    Takes a list of files and creates a list of graft points. This is used to keep the directory
    structure within the target directory.

    Graft points in mkisofs:
    Assume the local file ../old.lis exists, and we want to include it on the ISO.

        foo/bar/=../old.lis

    will include old.lis in the ISO as /foo/bar/old.lis, while

        foo/bar/new_name=../old.lis

    will include ../old.lis as /foo/bar/new_name on the ISO.

    :param img_file_paths:  A list of files paths to graft. These are expected to be the full path to
                                each file, and should be somewhere in the target directory
    :type  img_file_paths:  list
    :param target_dir:      The full path to the target directory
    :type  target_dir:      str

    :return: A list of graft points, which are str in the format 'relative_path/=file_path'
    :rtype:  list
    """
    grafts = []
    for path in img_file_paths:
        relative_path = os.path.relpath(os.path.dirname(path), target_dir)
        grafts.append("/%s/=%s" % (relative_path, path))
    return grafts


def _get_pathspec_file(file_list, target_dir):
    """
    This creates a pathspec file with all the grafts and returns the full path to the file. If an error
    occurs while writing to the temporary file, the temporary file is cleaned up and the exception is
    re-raised. Otherwise, it is the responsibility of the caller to clean up the temporary file.

    A pathspec in mkisofs:
    pathspec is the path of the directory tree to be copied into the ISO9660 filesystem. Multiple
    paths can be specified, and mkisofs will merge the files found in all of the specified path
    components to form the filesystem image.

    A pathspec file consists of a list of paths to be copied into the filesystem.

    :param file_list:  A list of full paths to the files to be placed in the pathspec file.
    :type  file_list:  list
    :param target_dir: The full path to the target directory
    :type  target_dir: str

    :return: The absolute path of the temporary pathspec file. This is the responsibility of the caller
                to clean up.
    :rtype:  str
    """
    # file_descriptor is of type int, not file, so use os.write and os.close
    file_descriptor, file_path = tempfile.mkstemp(dir=target_dir, prefix='pulpiso-')

    # Try to retrieve and write the grafts, but if we fail, clean up
    try:
        # Retrieve the grafts for the given file list and write them to the temporary file
        grafts = _get_grafts(file_list, target_dir)
        for graft in grafts:
            os.write(file_descriptor, graft + '\n')
    except (OSError, IOError):
        # If something went wrong, clean up the temporary file and re-raise the exception
        os.close(file_descriptor)
        os.unlink(file_path)
        raise

    os.close(file_descriptor)

    return file_path


def _get_dir_file_list_and_size(target_dir):
    """
    Walks the given directory and makes a list of each file in the directory, as well as its size

    :param target_dir: The full path to the directory to walk
    :type  target_dir: str

    :return: A tuple in the form (list, int) where the list is a list of tuples of (file_path, file_size)
                and the int is the total size of the directory
    :rtype:  tuple
    """
    total_size = 0
    top_directory = os.path.abspath(os.path.normpath(target_dir))
    file_list = []
    for root, dirs, files in os.walk(top_directory):
        for f in files:
            file_path = os.path.join(root, f)
            size = os.stat(file_path)[ST_SIZE]
            file_list.append((file_path, size))
            total_size += size
    return file_list, total_size
