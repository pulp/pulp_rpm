import tempfile

from django.conf import settings
from pulpcore.app.models.content import SigningService
from pulpcore.exceptions.validation import ValidationError

from pulp_rpm.app.shared_utils import RpmTool, write_unsigned_rpm_package


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
            with tempfile.NamedTemporaryFile(dir=temp_directory_name) as temp_file:
                # get rpm package file
                write_unsigned_rpm_package(temp_file)

                # sign it with this service
                return_value = self.sign(temp_file.name)
                try:
                    return_value["rpm_package"]
                except KeyError:
                    raise ValidationError(f"Malformed output from signing script: {return_value}")

                # verify with rpm tool
                with tempfile.NamedTemporaryFile(dir=temp_directory_name) as pubkey_file:
                    pubkey_file.write(self.public_key.encode())
                    pubkey_file.flush()
                    rpm_tool = RpmTool()
                    rpm_tool.import_pubkey(pubkey_file.name)
                    rpm_tool.verify_signature(temp_file.name)
