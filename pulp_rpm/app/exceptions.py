from gettext import gettext as _

from pulpcore.plugin.exceptions import PulpException


class AdvisoryConflict(PulpException):
    """
    Raised when two advisories conflict in a way that Pulp can't resolve it.
    """

    error_code = "RPM0001"

    def __init__(self, msg):
        super().__init__()
        """
        Set the exception identifier.

        Args:
            msg(str): Detailed message about the reasons for Advisory conflict
        """
        self.msg = msg

    def __str__(self):
        """
        Return a message for the exception.
        """
        return f"[{self.error_code}] " + self.msg


class DistributionTreeConflict(FileNotFoundError):
    """
    Raised when two or more distribution trees are being added to a repository version.
    """

    error_code = "RPM0002"

    def __str__(self):
        """
        Return a message for the exception.
        """
        return f"[{self.error_code}] " + _(
            "More than one distribution tree cannot be added to a repository version."
        )


class UlnCredentialsError(PulpException):
    """
    Raised when no valid ULN Credentials were given.
    """

    error_code = "RPM0003"

    def __str__(self):
        """
        Return a message for the exception.
        """
        return f"[{self.error_code}] " + _("No valid ULN credentials given.")


class RemoteFetchError(PulpException):
    """
    Raised when a remote URL fetch fails with an HTTP error.
    """

    error_code = "RPM0004"

    def __init__(self, url, status, message):
        super().__init__()
        """
        Set the exception details.

        Args:
            url(str): The URL that failed
            status(int): HTTP status code
            message(str): Error message
        """
        self.url = url
        self.status = status
        self.message = message

    def __str__(self):
        """
        Return a message for the exception.
        """
        return f"[{self.error_code}] " + _(
            "Failed to fetch from remote URL '{url}': {status} - {message}"
        ).format(url=self.url, status=self.status, message=self.message)


class MirrorIncompatibleRepositoryError(PulpException):
    """
    Raised when repository uses features incompatible with mirror sync.
    """

    error_code = "RPM0006"

    def __str__(self):
        """
        Return a message for the exception.
        """
        return f"[{self.error_code}] " + _(
            "This repository uses features which are incompatible with 'mirror' sync. "
            "Please sync without mirroring enabled."
        )


class PackageSignatureVerificationError(PulpException):
    """
    Raised when package signature verification fails.
    """

    error_code = "RPM0007"

    def __init__(self, stdout, stderr):
        super().__init__()
        """
        Set the exception details.

        Args:
            stdout(str): Standard output from verification
            stderr(str): Standard error from verification
        """
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        """
        Return a message for the exception.
        """
        return f"[{self.error_code}] " + _(
            "Failed to verify package signature: {stdout} {stderr}."
        ).format(stdout=self.stdout, stderr=self.stderr)


class SigningScriptError(PulpException):
    """
    Raised when signing script fails to create a signed package.
    """

    error_code = "RPM0008"

    def __init__(self, result):
        super().__init__()
        """
        Set the exception details.

        Args:
            result(str): Result from signing script
        """
        self.result = result

    def __str__(self):
        """
        Return a message for the exception.
        """
        return f"[{self.error_code}] " + _(
            "Signing script did not create the signed package: {result}"
        ).format(result=self.result)


class ChecksumTooShortError(PulpException):
    """
    Raised when a checksum is too short for the requested layout.
    """

    error_code = "RPM0009"

    def __init__(self, checksum, layout):
        super().__init__()
        """
        Set the exception details.

        Args:
            checksum(str): The short checksum
            layout(str): The layout type
        """
        self.checksum = checksum
        self.layout = layout

    def __str__(self):
        """
        Return a message for the exception.
        """
        return f"[{self.error_code}] " + _(
            "Checksum {checksum} is unknown or too short to use for {layout} publishing."
        ).format(checksum=self.checksum, layout=self.layout)


class ForbiddenChecksumTypeError(PulpException):
    """
    Raised when a package contains a forbidden checksum type.
    """

    error_code = "RPM0010"

    def __init__(self, pkgid, content_unit_id, checksum_type, error_msg):
        super().__init__()
        """
        Set the exception details.

        Args:
            pkgid(str): Package ID
            content_unit_id(str): Content unit ID
            checksum_type(str): The forbidden checksum type
            error_msg(str): Additional error message
        """
        self.pkgid = pkgid
        self.content_unit_id = content_unit_id
        self.checksum_type = checksum_type
        self.error_msg = error_msg

    def __str__(self):
        """
        Return a message for the exception.
        """
        return f"[{self.error_code}] " + _(
            "Package with pkgId {pkgid} as content unit {content_unit_id} contains forbidden "
            "checksum type '{checksum_type}', thus can't be published. {error_msg}"
        ).format(
            pkgid=self.pkgid,
            content_unit_id=self.content_unit_id,
            checksum_type=self.checksum_type,
            error_msg=self.error_msg,
        )


class UnsupportedLayoutError(PulpException):
    """
    Raised when an unsupported layout value is used.
    """

    error_code = "RPM0011"

    def __init__(self, layout):
        super().__init__()
        """
        Set the exception details.

        Args:
            layout(str): The unsupported layout value
        """
        self.layout = layout

    def __str__(self):
        """
        Return a message for the exception.
        """
        return f"[{self.error_code}] " + _(
            "Layout value {layout} is unsupported by this version"
        ).format(layout=self.layout)


class DisallowedChecksumTypeError(PulpException):
    """
    Raised when a disallowed checksum type is requested for publication.
    """

    error_code = "RPM0012"

    def __init__(self, checksum_type, error_msg):
        super().__init__()
        """
        Set the exception details.

        Args:
            checksum_type(str): The disallowed checksum type
            error_msg(str): Additional error message
        """
        self.checksum_type = checksum_type
        self.error_msg = error_msg

    def __str__(self):
        """
        Return a message for the exception.
        """
        return f"[{self.error_code}] " + _(
            "Disallowed checksum type '{checksum_type}' was requested to be used for "
            "publication: {error_msg}"
        ).format(checksum_type=self.checksum_type, error_msg=self.error_msg)


class SignatureFileEmptyError(PulpException):
    """
    Raised when a signature file is 0 bytes.
    """

    error_code = "RPM0013"

    def __str__(self):
        """
        Return a message for the exception.
        """
        return f"[{self.error_code}] " + _("Signature file is 0 bytes")


class MissingPrimaryMetadataError(PulpException):
    """
    Raised when a repository is missing the required primary.xml metadata file.
    """

    error_code = "RPM0016"

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Repository doesn't contain required metadata file 'primary.xml'"
        )


class UnsupportedZckCompressionError(PulpException):
    """
    Raised when modular data is compressed with ZCK, which is not supported.
    """

    error_code = "RPM0017"

    def __str__(self):
        return f"[{self.error_code}] " + _("Modular data compressed with ZCK is not supported.")


class UnsupportedChecksumTypeError(PulpException):
    """
    Raised when an advisory package uses an unsupported checksum type.
    """

    error_code = "RPM0018"

    def __init__(self, sum_type):
        super().__init__()
        self.sum_type = sum_type

    def __str__(self):
        return f"[{self.error_code}] " + _('"{sum_type}" is not supported.').format(
            sum_type=self.sum_type
        )
