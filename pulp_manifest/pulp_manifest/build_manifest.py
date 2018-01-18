import argparse
import os
import sys
from hashlib import sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", help="A path to the directory where the PULP_MANIFEST"
                                          " file should be created.")
    args = parser.parse_args()
    directory = os.path.abspath(args.directory)

    # Remove PULP_MANIFEST if it already exists in the given directory
    try:
        os.remove(os.path.join(directory, 'PULP_MANIFEST'))
    except (IOError, OSError):
        pass

    try:
        manifest = traverse_dir(directory)
        with open(os.path.join(directory, 'PULP_MANIFEST'), 'w+') as fp:
            for line in manifest:
                fp.write(line + os.linesep)
    except (IOError, OSError) as e:
        print("Couldn't open or write PULP_MANIFEST to directory %s (%s)." % (directory, e))
        sys.exit(1)


def get_digest(path):
    """
    Get the sha256 digest of the file at path.

    :param path: str of the file path that we need the digest for
    :return: str that is the file digest
    """
    digest = sha256()
    with open(path) as fp:
        digest.update(fp.read())
    return digest.hexdigest()


def traverse_dir(directory):
    """
    Traverse a given directory path and generate the PULP_MANIFEST
    associated with it.

    :param directory: str
    :return: list of pulp manifest items
    """
    manifest = []
    for root, dirs, files in os.walk(directory, followlinks=True):
        for file in files:
            file_path = os.path.join(root, file)
            line = []

            line.append(os.path.relpath(file_path, directory))
            line.append(get_digest(file_path))
            line.append(os.path.getsize(file_path))
            manifest.append(",".join(str(item) for item in line))
    return manifest
