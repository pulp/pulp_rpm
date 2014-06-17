from gettext import gettext as _

from pulp.common.error_codes import Error


# Create a section for general validation errors (RPM1000 - RPM2999)
# Validation problems should be reported with a general PLP1000 error with a more specific
# error message nested inside of it.
RPM1001 = Error("RPM1001", _("Error occurred parsing pulp_distribution.xml from feed: %(feed)s"),
                ['feed'])
