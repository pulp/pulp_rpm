from ConfigParser import SafeConfigParser
import logging

from pulp_rpm.common import constants
from pulp.repoauth.protected_repo_utils import ProtectedRepoUtils
from pulp.repoauth.repo_cert_utils import RepoCertUtils


logger = logging.getLogger(__name__)

BUILD_DIRNAME = 'build'


def configure_repository_protection(repo, authorization_ca_cert):
    """
    Configure this repository to be protected by registering it with the repo protection
    application. Repository protection will be performed if the CONFIG_SSL_AUTH_CA_CERT option is
    set to a certificate. Otherwise, this method removes repository protection.

    :param repo:                  The repository that is being protected
    :type  repo:                  pulp.plugins.model.Repository
    :param authorization_ca_cert: The CA certificate that should be used to protect the repository
                                  Client certificates must be signed by this certificate.
    :type  authorization_ca_cert: basestring
    """
    repo_cert_utils, protected_repo_utils = _get_repository_protection_utils()
    relative_path = _get_relative_path(repo)

    # If we want to include a valid entitlement certificate to hand to consumers, use the key
    # "cert". For now, we only support the "ca" flag for validating the client certificates.
    cert_bundle = {'ca': authorization_ca_cert}

    # This will put the certificates on the filesystem so the repo protection application can
    # use them to validate the consumers' entitlement certificates
    repo_cert_utils.write_consumer_cert_bundle(repo.id, cert_bundle)
    # Add this repository to the protected list. This will tell the repo protection application
    # that it should enforce protection on this relative path
    protected_repo_utils.add_protected_repo(relative_path, repo.id)


def _get_relative_path(repo):
    """
    Return the relative path for a particular repository.

    :param repo: The repo we need hosting locations for
    :type  repo: pulp.server.db.model.Repository
    :return:     relative path for the repo
    :rtype:      basestring
    """
    return repo.repo_id


def _get_repository_protection_utils():
    """
    Instantiate our repository protection utilities with the config file.

    :return: A 2-tuple of repo_cert_utils and protected_repo_utils
    :rtype:  tuple
    """
    repo_auth_config = SafeConfigParser()
    repo_auth_config.read(constants.REPO_AUTH_CONFIG_FILE)
    repo_cert_utils = RepoCertUtils(repo_auth_config)
    protected_repo_utils = ProtectedRepoUtils(repo_auth_config)

    return repo_cert_utils, protected_repo_utils


def remove_repository_protection(repo):
    """
    Remove repository protection from the given repository.

    :param repo: The repository to remove protection from
    :type  repo: pulp.server.db.model.Repository
    """
    protected_repo_utils = _get_repository_protection_utils()[1]
    relative_path = _get_relative_path(repo)
    # Ensure that we aren't protecting this path
    protected_repo_utils.delete_protected_repo(relative_path)
