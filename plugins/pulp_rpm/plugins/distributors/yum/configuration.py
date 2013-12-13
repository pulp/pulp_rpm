# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software;
# if not, see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import os
import re
from ConfigParser import SafeConfigParser
from gettext import gettext as _

from pulp.server.managers import factory

from pulp_rpm.common.constants import SCRATCHPAD_DEFAULT_METADATA_CHECKSUM, \
    CONFIG_DEFAULT_CHECKSUM, CONFIG_KEY_CHECKSUM_TYPE, REPO_AUTH_CONFIG_FILE
from pulp_rpm.common.ids import TYPE_ID_DISTRIBUTOR_YUM
from pulp_rpm.repo_auth import protected_repo_utils, repo_cert_utils
from pulp_rpm.yum_plugin import util

# -- constants -----------------------------------------------------------------

_LOG = util.getLogger(__name__)

REQUIRED_CONFIG_KEYS = ('relative_url', 'http', 'https')

OPTIONAL_CONFIG_KEYS = ('auth_ca', 'auth_cert', 'checksum_type',
                        'http_publish_dir', 'https_publish_dir', 'protected',
                        'skip', 'skip_pkg_tags', 'use_createrepo')

ALPHA_NUMERIC_PATH_REGEX = re.compile(r'^[a-zA-Z0-9/_-]+$')

ROOT_PUBLISH_DIR = '/var/lib/pulp/published/yum'
MASTER_PUBLISH_DIR = os.path.join(ROOT_PUBLISH_DIR, 'master')
HTTP_PUBLISH_DIR = os.path.join(ROOT_PUBLISH_DIR, 'http', 'repos')
HTTPS_PUBLISH_DIR = os.path.join(ROOT_PUBLISH_DIR, 'https', 'repos')

# -- public api ----------------------------------------------------------------

def load_config(config_file_path):
    """
    Load and return a config parser for the given configuration file path.

    :param config_file_path: full path to the configuration file
    :type  config_file_path: str
    :return: Parser representing the parsed configuration file
    :rtype:  SafeConfigParser
    """
    _LOG.debug('Loading configuration file: %s' % config_file_path)

    config = SafeConfigParser()

    if os.access(config_file_path, os.F_OK | os.R_OK):
        config.read(config_file_path)

    else:
        _LOG.warning(_('Could not load config file: %(f)s') % {'f': config_file_path})

    return config


def validate_config(repo, config, config_conduit):
    """
    Validate the prospective configuration instance for the the give repository.

    :param repo: repository to validate the config for
    :type  repo: pulp.plugins.model.Repository
    :param config: configuration instance to validate
    :type  config: pulp.plugins.config.PluginCallConfiguration
    :param config_conduit: conduit providing access to relevant Pulp functionality
    :type  config_conduit: pulp.plugins.conduits.repo_config.RepoConfigConduit
    :return: tuple of (bool, str) stating that the configuration is valid or not and why
    :rtype:  tuple of (bool, str or None)
    """

    config = config.flatten() # squish it into a dictionary so we can manipulate it
    error_messages = []

    configured_keys = set(config)
    required_keys = set(REQUIRED_CONFIG_KEYS)
    supported_keys = set(REQUIRED_CONFIG_KEYS + OPTIONAL_CONFIG_KEYS)

    # check for any required options that are missing
    missing_keys = required_keys - configured_keys
    msg = _('Configuration key [%(k)s] is required, but was not provided')
    for key in missing_keys:
        error_messages.append(msg % {'k': key})

    # check for unsupported configuration options
    extraneous_keys = configured_keys - supported_keys
    msg = _('Configuration key [%(k)s] is not supported')
    for key in extraneous_keys:
        error_messages.append(msg % {'k': key})

    # when adding validation methods, make sure to register them here
    # yes, the individual sections are in alphabetical oder
    configured_key_validation_methods = {
        # required options
        'http': _validate_http,
        'https': _validate_https,
        'relative_url': _validate_relative_url,
        # optional options
        'auth_ca': _validate_auth_ca,
        'auth_cert': _validate_auth_cert,
        'checksum_type': _validate_checksum_type,
        'http_publish_dir': _validate_http_publish_dir,
        'https_publish_dir': _validate_https_publish_dir,
        'protected': _validate_protected,
        'skip': _validate_skip,
        'skip_pkg_tags': _validate_skip_pkg_tags,
        'use_createrepo': _validate_use_createrepo,
    }

    # iterate through the options that have validation methods and validate them
    for key, validation_method in configured_key_validation_methods.items():

        if key not in configured_keys:
            continue

        validation_method(config[key], error_messages)

    # check that the relative path does not conflict with any existing repos
    _check_for_relative_path_conflicts(repo, config, config_conduit, error_messages)

    # if we have errors, log them, and return False with a concatenated error message
    if error_messages:

        for msg in error_messages:
            _LOG.error(msg)

        return False, '\n'.join(error_messages)

    process_cert_based_auth(repo, config)
    return True, None


def process_cert_based_auth(repo, config):
    """
    Write the CA and Cert files in the PKI, if present. Remove them, if not.

    :param repo: repository to validate the config for
    :type  repo: pulp.plugins.model.Repository
    :param config: configuration instance to validate
    :type  config: pulp.plugins.config.PluginCallConfiguration or dict
    """

    auth_ca = config.get('auth_ca', None)
    auth_cert = config.get('auth_cert', None)

    relative_path = get_repo_relative_path(repo, config)
    auth_config = load_config(REPO_AUTH_CONFIG_FILE)

    protected_repo_utils_instance = protected_repo_utils.ProtectedRepoUtils(auth_config)

    if None in (auth_ca, auth_cert):
        protected_repo_utils_instance.delete_protected_repo(relative_path)

    else:
        repo_cert_utils_instance = repo_cert_utils.RepoCertUtils(auth_config)
        bundle = {'ca': auth_ca, 'cert': auth_cert}

        repo_cert_utils_instance.write_consumer_cert_bundle(repo.id, bundle)
        protected_repo_utils_instance.add_protected_repo(relative_path, repo.id)


def get_master_publish_dir(repo):
    """
    Get the master publishing directory for the given repository.

    :param repo: repository to get the master publishing directory for
    :type  repo: pulp.plugins.model.Repository
    :return: master publishing directory for the given repository
    :rtype:  str
    """

    return os.path.join(MASTER_PUBLISH_DIR, repo.id)


def get_http_publish_dir(config=None):
    """
    Get the configured HTTP publication directory.
    Returns the global default if not configured.

    :param config: configuration instance
    :type  config: pulp.plugins.config.PluginCallConfiguration or None
    :return: the HTTP publication directory
    :rtype:  str
    """

    config = config or {}

    publish_dir = config.get('http_publish_dir', HTTP_PUBLISH_DIR)

    if publish_dir != HTTP_PUBLISH_DIR:
        msg = _('Overridden configuration value for [http_publish_dir] provided: %(v)s')
        _LOG.debug(msg % {'v': publish_dir})

    return publish_dir


def get_https_publish_dir(config=None):
    """
    Get the configured HTTPS publication directory.
    Returns the global default if not configured.

    :param config: configuration instance
    :type  config: pulp.plugins.config.PluginCallConfiguration or None
    :return: the HTTPS publication directory
    :rtype:  str
    """

    config = config or {}

    publish_dir = config.get('https_publish_dir', HTTPS_PUBLISH_DIR)

    if publish_dir != HTTPS_PUBLISH_DIR:
        msg = _('Overridden configuration value for [https_publish_dir] provided: %(v)s')
        _LOG.debug(msg % {'v': publish_dir})

    return publish_dir


def get_repo_relative_path(repo, config=None):
    """
    Get the configured relative path for the given repository.
    :param repo: repository to get relative path for
    :type  repo: pulp.plugins.model.Repository
    :param config: configuration instance for the repository
    :type  config: pulp.plugins.config.PluginCallConfiguration or dict or None
    :return: relative path for the repository
    :rtype:  str
    """

    config = config or {}
    relative_path = config.get('relative_url', repo.id) or repo.id

    if relative_path.startswith('/'):
        relative_path = relative_path[1:]

    return relative_path


def get_repo_checksum_type(publish_conduit, config):
    """
    Lookup checksum type on the repo to use for metadata generation;
    importer sets this value if available on the repo scratchpad.

    WARNING: This method has a side effect of saving the checksum type on the distributor
    config if a checksum has not already been set on the distributor config.

    :param config: publish conduit
    :type  config: pulp.plugins.conduits.repo_publish.RepoPublishConduit

    :param config: plugin configuration
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :return the type of checksum to use for the repository
    :rtype str
    """
    checksum_type = config.get(CONFIG_KEY_CHECKSUM_TYPE)
    if not checksum_type:
        scratchpad_data = publish_conduit.get_repo_scratchpad()
        if not scratchpad_data or SCRATCHPAD_DEFAULT_METADATA_CHECKSUM not in scratchpad_data:
            checksum_type = CONFIG_DEFAULT_CHECKSUM
        else:
            checksum_type = scratchpad_data[SCRATCHPAD_DEFAULT_METADATA_CHECKSUM]

    if checksum_type == 'sha':
        checksum_type = 'sha1'

    distributor_config = config.repo_plugin_config
    if 'checksum_type' not in distributor_config:
        distributor_manager = factory.repo_distributor_manager()
        distributor = distributor_manager.get_distributor(publish_conduit.repo_id,
                                                              publish_conduit.distributor_id)
        if distributor['distributor_type_id'] == TYPE_ID_DISTRIBUTOR_YUM:
            distributor_manager.update_distributor_config(publish_conduit.repo_id,
                                                      publish_conduit.distributor_id,
                                                      {'checksum_type': checksum_type})
    return checksum_type


# -- required config validation ------------------------------------------------

def _validate_http(http, error_messages):
    _validate_boolean('http', http, error_messages)


def _validate_https(https, error_messages):
    _validate_boolean('https', https, error_messages)


def _validate_relative_url(relative_url, error_messages):

    if relative_url is None:
        return

    if not isinstance(relative_url, basestring):
        msg = _('Configuration value for [relative_url] must be a string, but is a %(t)s')
        error_messages.append(msg % {'t': str(type(relative_url))})

    elif not ALPHA_NUMERIC_PATH_REGEX.match(relative_url):
        msg = _('Configuration value for [relative_url] may only contain alphanumerics, underscores, dashes, and slashes')
        error_messages.append(msg)

# -- optional config validation ------------------------------------------------

def _validate_auth_ca(auth_ca, error_messages):
    _validate_certificate('auth_ca', auth_ca, error_messages)


def _validate_auth_cert(auth_cert, error_messages):
    _validate_certificate('auth_cert', auth_cert, error_messages)


def _validate_checksum_type(checksum_type, error_messages):

    if checksum_type is None or util.is_valid_checksum_type(checksum_type):
        return

    msg = _('Configuration value for [checksum_type] is not supported: %(c)s')
    error_messages.append(msg % {'c': str(checksum_type)})


def _validate_http_publish_dir(http_publish_dir, error_messages):
    _validate_usable_directory('http_publish_dir', http_publish_dir, error_messages)


def _validate_https_publish_dir(https_publish_dir, error_messages):
    _validate_usable_directory('https_publish_dir', https_publish_dir, error_messages)


def _validate_protected(protected, error_messages):
    _validate_boolean('protected', protected, error_messages, False)


def _validate_skip(skip, error_messages):
    _validate_list('skip', skip, error_messages, False)


def _validate_skip_pkg_tags(skip_pkg_tags, error_messages):
    _validate_boolean('skip_pkg_tags', skip_pkg_tags, error_messages)


def _validate_use_createrepo(use_createrepo, error_messages):
    _validate_boolean('use_createrepo', use_createrepo, error_messages, False)

# -- generalized validation methods --------------------------------------------

def _validate_boolean(key, value, error_messages, none_ok=True):

    if isinstance(value, bool) or (none_ok and value is None):
        return

    msg = _('Configuration value for [%(k)s] should a boolean, but is a %(t)s')
    error_messages.append(msg % {'k': key, 't': str(type(value))})


def _validate_list(key, value, error_messages, none_ok=True):
    if isinstance(value, list) or (none_ok and value is None):
        return
    msg = _('Configuration value for [%(k)s] should be a list, but is a %(t)s')
    error_messages.append(msg % {'k': key, 't': str(type(value))})


def _validate_dictionary(key, value, error_messages, none_ok=True):

    if isinstance(value, dict) or (none_ok and value is None):
        return

    msg = _('Configuration value for [%(k)s] should be a dictionary, but is a %(t)s')
    error_messages.append(msg % {'k': key, 't': str(type(value))})


def _validate_certificate(key, cert, error_messages):

    cert = cert.encode('utf-8')

    if util.validate_cert(cert):
        return

    msg = _('Configuration value for [%(k)s] is not a valid certificate')
    error_messages.append(msg % {'k': key})


def _validate_usable_directory(key, path, error_messages):

    if not os.path.exists(path) or not os.path.isdir(path):
        msg = _('Configuration value for [%(k)s] must be an existing directory')
        error_messages.append(msg % {'k': key})

    elif not os.access(path, os.R_OK | os.W_OK):
        msg = _('Configuration value for [%(k)s] must be a directory that is readable and writable')
        error_messages.append(msg % {'k': key})

# -- check for conflicting relative paths --------------------------------------

def _check_for_relative_path_conflicts(repo, config, config_conduit, error_messages):

    relative_path = get_repo_relative_path(repo, config)
    conflicting_distributors = config_conduit.get_repo_distributors_by_relative_url(relative_path, repo.id)

    # in all honesty, this loop should execute at most once
    # but it may be interesting/useful for erroneous situations
    for distributor in conflicting_distributors:
        conflicting_repo_id = distributor['repo_id']
        conflicting_relative_url = distributor['config']['relative_url'] or conflicting_repo_id
        msg = _('Relative URL [%(p)s] for repository [%(r)s] conflicts with existing relative URL [%(u)s] for repository [%(c)s]')
        error_messages.append(msg % {'p': relative_path, 'r': repo.id, 'u': conflicting_relative_url, 'c': conflicting_repo_id})

