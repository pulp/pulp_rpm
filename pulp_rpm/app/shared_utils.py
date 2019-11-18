import createrepo_c
import os
import tempfile
import shutil

from pulp_rpm.app.models import Package


def _prepare_package(artifact, filename):
    """
    Helper function for creating package.

    Copy file to a temp directory under
    the user provided filename.

    Returns: artifact model as dict

    Args:
        artifact: inited and validated artifact to save
        filename: name of file uploaded by user
    """
    # Copy file to a temp directory under the user provided filename
    with tempfile.TemporaryDirectory() as td:
        temp_path = os.path.join(td, filename)
        shutil.copy2(artifact.file.path, temp_path)
        cr_pkginfo = createrepo_c.package_from_rpm(temp_path)

        package = Package.createrepo_to_dict(cr_pkginfo)

    package['location_href'] = filename
    return package
