from gettext import gettext as _

from pulpcore.plugin.exceptions import PulpException


class AdvisoryConflict(PulpException):
    """
    Raised when two advisories conflict in a way that Pulp can't resolve it.
    """

    error_code = "RPM0001"

    def __init__(self, msg):
        super().__init__()
        self.msg = msg

    def __str__(self):
        return f"[{self.error_code}] " + self.msg


class DistributionTreeConflict(FileNotFoundError):
    """
    Raised when two or more distribution trees are being added to a repository version.
    """

    error_code = "RPM0002"

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "More than one distribution tree cannot be added to a repository version."
        )


class UlnCredentialsError(PulpException):
    """
    Raised when no valid ULN Credentials were given.
    """

    error_code = "RPM0003"

    def __str__(self):
        return f"[{self.error_code}] " + _("No valid ULN credentials given.")


class RemoteFetchError(PulpException):
    """
    Raised when a remote URL fetch fails with an HTTP error.
    """

    error_code = "RPM0004"

    def __init__(self, url, status, message, context=None):
        super().__init__()
        self.url = url
        self.status = status
        self.message = message
        self.context = context

    def __str__(self):
        msg = _("Failed to fetch from remote URL '{url}': {status} - {message}").format(
            url=self.url, status=self.status, message=self.message
        )
        if self.context:
            msg = f"{self.context}: {msg}"
        return f"[{self.error_code}] " + msg


class MirrorIncompatibleRepositoryError(PulpException):
    """
    Raised when repository uses features incompatible with mirror sync.
    """

    error_code = "RPM0006"

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "This repository uses features which are incompatible with 'mirror' sync. "
            "Please sync without mirroring enabled."
        )


class PackageSigningError(PulpException):
    """
    Raised when signing script fails to create a signed package.
    """

    error_code = "RPM0008"

    def __init__(self, result):
        super().__init__()
        self.result = result

    def __str__(self):
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
        self.checksum = checksum
        self.layout = layout

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Checksum {checksum} is unknown or too short to use for {layout} publishing."
        ).format(checksum=self.checksum, layout=self.layout)


class ForbiddenChecksumTypeError(PulpException):
    """
    Raised when a checksum type is not allowed for publishing.
    """

    error_code = "RPM0010"

    def __init__(self, checksum_type, detail):
        super().__init__()
        self.checksum_type = checksum_type
        self.detail = detail

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Checksum type '{checksum_type}' is not allowed: {detail}"
        ).format(checksum_type=self.checksum_type, detail=self.detail)


class UnsupportedLayoutError(PulpException):
    """
    Raised when an unsupported layout value is used.
    """

    error_code = "RPM0011"

    def __init__(self, layout):
        super().__init__()
        self.layout = layout

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Layout value {layout} is unsupported by this version"
        ).format(layout=self.layout)


class MetadataSigningError(PulpException):
    """
    Raised when metadata signing produces an invalid result.
    """

    error_code = "RPM0013"

    def __init__(self, detail):
        super().__init__()
        self.detail = detail

    def __str__(self):
        return f"[{self.error_code}] " + _("Metadata signing failed: {detail}").format(
            detail=self.detail
        )


class MissingPrimaryMetadataError(PulpException):
    """
    Raised when a repository is missing the required primary.xml metadata file.
    """

    error_code = "RPM0016"

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Repository doesn't contain required metadata file 'primary.xml'"
        )


class UnsupportedModularCompressionError(PulpException):
    """
    Raised when modular data uses an unsupported compression format.
    """

    error_code = "RPM0017"

    def __init__(self, compression_type):
        super().__init__()
        self.compression_type = compression_type

    def __str__(self):
        return f"[{self.error_code}] " + _(
            "Modular data compressed with {compression_type} is not supported."
        ).format(compression_type=self.compression_type)


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
