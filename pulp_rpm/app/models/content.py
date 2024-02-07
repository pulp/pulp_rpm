import subprocess
import tempfile
from pathlib import Path

import requests
from django.conf import settings
from pulpcore.app.models.content import SigningService
from pulpcore.exceptions.validation import (InvalidSignatureError,
                                            ValidationError)

RPM_PACKAGE_FIXTURE = Path("some-rpm-package.rpm")


def write_unsigned_rpm_package(temp_file: "BufferedRandom") -> Path:
    RPM_PACKAGE_URL = "https://raw.githubusercontent.com/pulp/pulp-fixtures/master/rpm/assets/bear-4.1-1.noarch.rpm"  # noqa: E501
    response = requests.get(RPM_PACKAGE_URL)
    response.raise_for_status()
    data = response.content
    temp_file.write(data)
    temp_file.flush()
    return temp_file


class RpmTool:
    """
    A wrapper utility for rpm cli tool.
    """

    def __init__(self):
        completed_process = subprocess.run(["which", "rpmsign"])
        if completed_process.returncode != 0:
            raise RuntimeError("Rpm cli tool is not installed on your system.")

    def import_pubkey(self, pubkey: str):
        """
        Parameters:
            import_pubkey: The public key file in ascii-armored format.
        """
        cmd = ("rpm", "--import", pubkey)
        completed_process = subprocess.run(cmd)
        if completed_process.returncode != 0:
            raise RuntimeError(f"Could not import public key into rpm-tool: {repr(pubkey)}")

    def verify(self, rpm_package_file: str):
        """
        Verify that an Rpm Package is signed by some of the imported pubkey.

        $ rpm --checksig camel-0.1-1.noarch.rpm

        unsigned:
            returncode: 0
            output: "camel-0.1-1.noarch.rpm: digests OK"

        signed, but rpm doesnt have pubkey imported:
            returncode: 1
            output: "camel-0.1-1.noarch.rpm: digests SIGNATURES NOT OK"

        signed and rpm can validate:
            returncode: 0
            output: "camel-0.1-1.noarch.rpm: digests signatures OK"
        """
        cmd = ("rpm", "--checksig", rpm_package_file)
        completed_process = subprocess.run(cmd, capture_output=True)
        exitcode = completed_process.returncode
        output = completed_process.stdout.decode()
        if exitcode != 0:
            raise InvalidSignatureError(f"Signature is invalid or could not be verified: {output}")
        elif "signatures" not in output:
            raise InvalidSignatureError(f"The package is not signed: {output}")


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
                    rpm_tool.verify(temp_file.name)
