from gettext import gettext as _

from pulp.common.error_codes import Error


# Create a section for general validation errors (RPM1000 - RPM2999)
# Validation problems should be reported with a general PLP1000 error with a more specific
# error message nested inside of it.
RPM1001 = Error("RPM1001", _("Error occurred parsing pulp_distribution.xml from feed: %(feed)s"),
                ['feed'])
RPM1002 = Error("RPM1002", _("Error uploading an RPM.  The specified file is a source rpm"), [])
RPM1003 = Error("RPM1003", _("Error uploading an SRPM.  The specified file is a binary rpm"), [])
RPM1004 = Error("RPM1004", _("Error retrieving metadata: %(reason)s"), ['reason'])
RPM1005 = Error("RPM1005", _("Unable to sync a repository that has no feed."), [])
RPM1006 = Error("RPM1006", _("Could not parse repository metadata"), [])
