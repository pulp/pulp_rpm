from gettext import gettext as _
import os
import re

import isodate
from pulp.common import dateutils

from pulp_rpm.common import constants
from pulp_rpm.yum_plugin import util as yum_utils


_logger = yum_utils.getLogger(__name__)

ISO_NAME_REGEX = re.compile(r'^[_A-Za-z0-9-]+$')
ASSOCIATED_UNIT_DATE_KEYWORD = 'created'


def is_valid_prefix(file_prefix):
    """
    Used to check if the given file prefix is valid. A valid prefix contains only letters,
    numbers, _,
    and -

    :param file_prefix: The string used to prefix the export file(s)
    :type  file_prefix: str

    :return: True if the given file_prefix is a valid match; False otherwise
    :rtype:  bool
    """
    return ISO_NAME_REGEX.match(file_prefix) is not None


def validate_export_config(config):
    """
    Currently, the export configuration for a single repository is the same as the group export
    configuration. If this changes, this should be removed, and each distributor should get its
    own custom validation function.

    :param config:  The configuration to validate
    :type  config:  pulp.plugins.config.PluginCallConfiguration

    :return: a tuple in the form (bool, str) where bool is True if the config is valid. The str
            describes the error if the configuration is invalid. i18n is taken into account.
    :rtype:  tuple
    """
    # Check for the required configuration keys, as defined in constants
    for key in constants.EXPORT_REQUIRED_CONFIG_KEYS:
        if key not in config.keys():
            msg = _("Missing required configuration key: %(key)s" % {"key": key})
            _logger.error(msg)
            return False, msg
        value = config.get(key)
        if value is None:
            msg = _("Value for %(key)s cannot be None! Insert a valid value." % {"key": key})
            _logger.error(msg)
            return False, msg
        if key == constants.PUBLISH_HTTP_KEYWORD:
            if not isinstance(value, bool):
                msg = _("http should be a boolean; got %s instead" % value)
                _logger.error(msg)
                return False, msg
        if key == constants.PUBLISH_HTTPS_KEYWORD:
            if not isinstance(value, bool):
                msg = _("https should be a boolean; got %s instead" % value)
                _logger.error(msg)
                return False, msg

    # Check for optional and unsupported configuration keys.
    for key in config.keys():
        if key not in constants.EXPORT_REQUIRED_CONFIG_KEYS and \
                key not in constants.EXPORT_OPTIONAL_CONFIG_KEYS:
            msg = _("Configuration key '%(key)s' is not supported" % {"key": key})
            _logger.error(msg)
            return False, msg
        value = config.get(key)
        if value is None:
            msg = _("Value for %(key)s cannot be None! Insert a valid value." % {"key": key})
            _logger.error(msg)
            return False, msg
        if key == constants.SKIP_KEYWORD:
            if not isinstance(value, list):
                msg = _("skip should be a list; got %s instead" % value)
                _logger.error(msg)
                return False, msg
        if key == constants.ISO_PREFIX_KEYWORD:
            if not is_valid_prefix(str(value)):
                msg = _(
                    "iso_prefix is not valid; valid characters include %s" % ISO_NAME_REGEX.pattern)
                _logger.error(msg)
                return False, msg
        if key == constants.ISO_SIZE_KEYWORD:
            if int(value) < 1:
                msg = _('iso_size is not a positive integer')
                _logger.error(msg)
                return False, msg
        if key == constants.START_DATE_KEYWORD:
            try:
                dateutils.parse_iso8601_datetime(str(value))
            except isodate.ISO8601Error:
                msg = _('Start date is not a valid iso8601 datetime. Format: yyyy-mm-ddThh:mm:ssZ')
                return False, msg
        if key == constants.END_DATE_KEYWORD:
            try:
                dateutils.parse_iso8601_datetime(str(value))
            except isodate.ISO8601Error:
                msg = _('End date is not a valid iso8601 datetime. Format: yyyy-mm-ddThh:mm:ssZ')
                return False, msg
        if key == constants.EXPORT_DIRECTORY_KEYWORD:
            if not os.path.isabs(value):
                msg = _("Value for 'export_dir' must be an absolute path: %s" % value)
                return False, msg
        if key == constants.CREATE_PULP_MANIFEST:
            if not isinstance(value, bool):
                return False, _('Value for "manifest" must be a boolean.')

    return True, None


def create_date_range_filter(config):
    """
    Create a date filter based on start and end issue dates specified in the repo config. The
    returned
    filter is a dictionary which can be used directly in a mongo query.

    :param config: plugin configuration instance; the proposed repo configuration is found within
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :return: date filter dict with issued date ranges in mongo query format
    :rtype:  {}
    """
    start_date = config.get(constants.START_DATE_KEYWORD)
    end_date = config.get(constants.END_DATE_KEYWORD)
    date_filter = None
    if start_date and end_date:
        date_filter = {ASSOCIATED_UNIT_DATE_KEYWORD: {"$gte": start_date, "$lte": end_date}}
    elif start_date:
        date_filter = {ASSOCIATED_UNIT_DATE_KEYWORD: {"$gte": start_date}}
    elif end_date:
        date_filter = {ASSOCIATED_UNIT_DATE_KEYWORD: {"$lte": end_date}}
    return date_filter
