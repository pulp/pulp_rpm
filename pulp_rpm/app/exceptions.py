from gettext import gettext as _

from pulpcore.plugin.exceptions import PulpException


class AdvisoryConflict(PulpException):
    """
    Raised when two advisories conflict in a way that Pulp can't resolve it.
    """

    error_code = "RPM0001"

    def __init__(self, msg):
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
