import tempfile
from pathlib import Path

from django.conf import settings
from pulpcore.plugin.models import SigningService
from pulpcore.plugin.exceptions import PulpException

from pulp_rpm.app.shared_utils import RpmTool


class RpmPackageSigningService(SigningService):
    """
    A model used for signing RPM packages.
    """

    def validate(self):
        """
        Validate a signing service for a Rpm Package signature.

        The validation ensure that the sign() method returns a dict as follows:

        ```
        {"rpm_package": "package.rpm"}
        ```

        The method:
        - get an rpm file
        - sign it with this service
        - verify with `rpm --checksig <file>` (uses imported keys)
        """
        with tempfile.TemporaryDirectory(dir=settings.WORKING_DIRECTORY) as temp_directory_name:
            # get and sign sample rpm
            temp_file = RpmTool.get_empty_rpm(temp_directory_name)
            return_value = self.sign(temp_file)
            try:
                return_value["rpm_package"]
            except KeyError:
                raise PulpException(f"Malformed output from signing script: {return_value}")

            # verify with rpm tool
            rpm_tool = RpmTool(root=Path(temp_directory_name))
            rpm_tool.import_pubkey_string(self.public_key)
            rpm_tool.verify_signature(temp_file)
