from pulpcore.plugin.exceptions import PulpException


class AdvisoryConflict(PulpException):
    """
    Raised when two advisories conflict in a way that Pulp can't resolve it.
    """

    def __init__(self, msg):
        """
        Set the exception identifier.

        Args:
            msg(str): Detailed message about the reasons for Advisory conflict
        """
        super().__init__("RPM0001")
        self.msg = msg

    def __str__(self):
        """
        Return a message for the exception.
        """
        return self.msg


class DistributionTreeConflict(PulpException):
    """
    Raised when two or more distribution trees are being added to a repository version.
    """

    def __init__(self, msg):
        """
        Set the exception identifier.

        Args:
            msg(str): Detailed message about the reasons for Distribution Tree conflict
        """
        super().__init__("RPM0002")
        self.msg = msg

    def __str__(self):
        """
        Return a message for the exception.
        """
        return self.msg
