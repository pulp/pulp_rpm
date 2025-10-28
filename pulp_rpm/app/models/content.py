import tempfile
from pathlib import Path

from django.conf import settings
from django.db import models
from pulpcore.plugin.exceptions import PulpException
from pulpcore.plugin.models import BaseModel, Content, SigningService
from typing import Optional

from pulp_rpm.app.shared_utils import RpmTool


class RpmPackageSigningService(SigningService):
    """
    A model used for signing RPM packages.

    The pubkey_fingerprint should be passed explicitly in the sign method.
    """

    def _env_variables(self, env_vars=None):
        # Prevent the signing service pubkey to be used for signing a package.
        # The pubkey should be provided explicitly.
        _env_vars = {"PULP_SIGNING_KEY_FINGERPRINT": None}
        if env_vars:
            _env_vars.update(env_vars)
        return super()._env_variables(_env_vars)

    def sign(
        self,
        filename: str,
        env_vars: Optional[dict] = None,
        pubkey_fingerprint: Optional[str] = None,
    ):
        """
        Sign a package @filename using @pubkey_figerprint.

        Args:
            filename: The absolute path to the package to be signed.
            env_vars: (optional) Dict of env_vars to be passed to the signing script.
            pubkey_fingerprint: The V4 fingerprint that correlates with the private key to use.
        """
        if not pubkey_fingerprint:
            raise ValueError("A pubkey_fingerprint must be provided.")
        _env_vars = env_vars or {}
        _env_vars["PULP_SIGNING_KEY_FINGERPRINT"] = pubkey_fingerprint
        return super().sign(filename, _env_vars)

    def validate(self):
        """
        Validate a signing service for a Rpm Package signature.

        Specifically, it validates that self.signing_script can sign an rpm package with
        the sample key self.pubkey and that the self.sign() method returns:

        ```json
        {"rpm_package": "<path/to/package.rpm>"}
        ```

        See [RpmTool.verify_signature][] for the signature verificaton method used.
        """
        with tempfile.TemporaryDirectory(dir=settings.WORKING_DIRECTORY) as temp_directory_name:
            # get and sign sample rpm
            temp_file = RpmTool.get_empty_rpm(temp_directory_name)
            return_value = self.sign(temp_file, pubkey_fingerprint=self.pubkey_fingerprint)
            try:
                result = Path(return_value["rpm_package"])
            except KeyError:
                raise PulpException(f"Malformed output from signing script: {return_value}")

            if not result.exists():
                raise PulpException(f"Signed package not found: {result}")

            # verify with rpm tool
            rpm_tool = RpmTool(root=Path(temp_directory_name))
            rpm_tool.import_pubkey_string(self.public_key)
            rpm_tool.verify_signature(result)


class RpmPackageSigningResult(BaseModel):
    """
    A model used for storing the result of signing an RPM package.

    This allows us to avoid re-signing the same package multiple times by keeping a history of
    what's been signed before.

    Fields:
        original_package_sha256 (String):
            The sha256 digest of the original package artifact.
        package_signing_fingerprint (String):
            The fingerprint used to sign the package. This value is copied from the repo's
            package_signing_fingerprint field.

    Relations:
        result_package (ForeignKey):
            The resulting package that was signed by @package_signing_fingerprint.
    """

    original_package_sha256 = models.TextField(max_length=64)
    package_signing_fingerprint = models.TextField(max_length=40)
    result_package = models.ForeignKey(Content, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("original_package_sha256", "package_signing_fingerprint")
