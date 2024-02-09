import tempfile
import time

from django.conf import settings
from pulpcore.app.models.content import SigningService
from pulpcore.exceptions.validation import ValidationError

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
            # get rpm package file
            rpm_tool = RpmTool()
            temp_file = rpm_tool.get_empty_rpm(temp_directory_name)

            # sign it with this service
            return_value = self.sign(temp_file)
            try:
                return_value["rpm_package"]
            except KeyError:
                raise ValidationError(f"Malformed output from signing script: {return_value}")

            # verify with rpm tool
            rpm_tool.import_pubkey_string(self.public_key)
            rpm_tool.verify_signature(temp_file)
