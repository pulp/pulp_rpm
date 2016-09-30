#!/usr/bin/env python3

import argparse
import os
import sys
import xml.etree.cElementTree as ET


def create_manifest(parent_directory, files):
    """
    Create a .pulp_distribution.xml manifest in the specified directory
    for the given list of files/directories.  For each item in the file list, if it is
    a file then add the file to the list.  If it is a directory all files contained within that
    directory will be added.

    :param parent_directory: The directory where the .pulp_distribution.xml file will be created
    :type parent_directory: str
    :param files: list of relative paths from "parent_directory" to the files to be added
    :type files: list of str
    """
    # Validate the arguments
    if not os.path.exists(parent_directory):
        print 'Error reading directory: %s' % parent_directory

    for filename in files:
        full_path = os.path.join(parent_directory, filename)
        if not os.path.exists(full_path):
            print 'Error reading directory or file: %s' % full_path

    # Write out the .pulp_distribution.xml
    root = ET.Element("pulp_distribution", {'version': '1'})
    for filename in files:
        full_path = os.path.join(parent_directory, filename)
        if os.path.isfile(full_path):
            element = ET.SubElement(root, 'file')
            element.text = filename
        else:
            # get the list of all files under the directory
            # Add all the relative paths to those files
            for root_dir, dirs, files in os.walk(full_path):
                for walked_file in files:
                    rel_dir = os.path.relpath(root_dir, parent_directory)
                    rel_file = os.path.join(rel_dir, walked_file)
                    element = ET.SubElement(root, 'file')
                    element.text = rel_file

    tree = ET.ElementTree(root)
    tree.write(os.path.join(parent_directory, ".pulp_distribution.xml"))


def main():
    # Get the list of directories from the arguments
    # Get the starting directory
    parser = argparse.ArgumentParser()
    parser.add_argument("parent",
                        help="The path to the directory where the manifest will be created")
    parser.add_argument("files",  nargs='+',
                        help="Relative path from the context-root to the files & directories to "
                             "be added to the manifest")
    args = parser.parse_args()

    create_manifest(args.parent, args.files)



if __name__ == '__main__':
    sys.exit(main())
