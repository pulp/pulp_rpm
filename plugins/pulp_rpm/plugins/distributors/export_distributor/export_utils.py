from gettext import gettext as _
import os
import re

import isodate
from pulp.common import dateutils

from pulp_rpm.common import constants, ids
from pulp_rpm.yum_plugin import util as yum_utils


_logger = yum_utils.getLogger(__name__)

ISO_NAME_REGEX = re.compile(r'^[_A-Za-z0-9-]+$')
ASSOCIATED_UNIT_DATE_KEYWORD = 'created'


def is_valid_prefix(file_prefix):
    """
    Used to check if the given file prefix is valid. A valid prefix contains only letters, numbers, _,
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
        value = config.get(key)
        if value is None:
            msg = _("Missing required configuration key: %(key)s" % {"key": key})
            _logger.error(msg)
            return False, msg
        if key == constants.PUBLISH_HTTP_KEYWORD:
            config_http = config.get(key)
            if config_http is not None and not isinstance(config_http, bool):
                msg = _("http should be a boolean; got %s instead" % config_http)
                _logger.error(msg)
                return False, msg
        if key == constants.PUBLISH_HTTPS_KEYWORD:
            config_https = config.get(key)
            if config_https is not None and not isinstance(config_https, bool):
                msg = _("https should be a boolean; got %s instead" % config_https)
                _logger.error(msg)
                return False, msg

    # Check for optional and unsupported configuration keys.
    for key in config.keys():
        if key not in constants.EXPORT_REQUIRED_CONFIG_KEYS and \
                key not in constants.EXPORT_OPTIONAL_CONFIG_KEYS:
            msg = _("Configuration key '%(key)s' is not supported" % {"key": key})
            _logger.error(msg)
            return False, msg
        if key == constants.SKIP_KEYWORD:
            metadata_types = config.get(key)
            if metadata_types is not None and not isinstance(metadata_types, list):
                msg = _("skip should be a list; got %s instead" % metadata_types)
                _logger.error(msg)
                return False, msg
        if key == constants.ISO_PREFIX_KEYWORD:
            iso_prefix = config.get(key)
            if iso_prefix is not None and not is_valid_prefix(str(iso_prefix)):
                msg = _("iso_prefix is not valid; valid characters include %s" % ISO_NAME_REGEX.pattern)
                _logger.error(msg)
                return False, msg
        if key == constants.ISO_SIZE_KEYWORD:
            iso_size = config.get(key)
            if iso_size is not None and int(iso_size) < 1:
                msg = _('iso_size is not a positive integer')
                _logger.error(msg)
                return False, msg
        if key == constants.START_DATE_KEYWORD:
            start_date = config.get(key)
            if start_date:
                try:
                    dateutils.parse_iso8601_datetime(str(start_date))
                except isodate.ISO8601Error:
                    msg = _('Start date is not a valid iso8601 datetime. Format: yyyy-mm-ddThh:mm:ssZ')
                    return False, msg
        if key == constants.END_DATE_KEYWORD:
            end_date = config.get(key)
            if end_date:
                try:
                    dateutils.parse_iso8601_datetime(str(end_date))
                except isodate.ISO8601Error:
                    msg = _('End date is not a valid iso8601 datetime. Format: yyyy-mm-ddThh:mm:ssZ')
                    return False, msg
        if key == constants.EXPORT_DIRECTORY_KEYWORD:
            export_dir = config.get(key)
            if export_dir:
                # Check that the export directory exists and is read/writable
                export_dir = str(export_dir)
                if not os.path.isdir(export_dir):
                    msg = _("Value for 'export_dir' is not an existing directory: %s" % export_dir)
                    return False, msg
                if not os.access(export_dir, os.R_OK) or not os.access(export_dir, os.W_OK):
                    msg = _("Unable to read & write to specified 'export_dir': %s" % export_dir)
                    return False, msg

    return True, None


def create_date_range_filter(config):
    """
    Create a date filter based on start and end issue dates specified in the repo config. The returned
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

