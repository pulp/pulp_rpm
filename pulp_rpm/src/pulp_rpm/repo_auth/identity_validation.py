#
# Copyright (c) 2011 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

'''
Logic for checking if a client certificate is an identity certificate.
Identity certificates are meant to be used by other Pulp components
to grant access without needing to care about specific entitlements.

The is_valid method is the logic driver. It performs the following functions:
  - DOES NOT validate the client certificate against the CA certificate
    configured for Pulp
  - Ensures the CN of the certificate matches the identity string
'''

from pulp_rpm.repo_auth.rhsm import certificate


IDENTITY_CN = 'pulp-identity'


# -- framework -----------------------------------------------------------------

def authenticate(environ):
    '''
    Framework hook method.
    '''
    cert_pem = environ["mod_ssl.var_lookup"]("SSL_CLIENT_CERT")

    return _is_valid(cert_pem)

# -- private -------------------------------------------------------------------

def _is_valid(cert_pem):
    '''
    validates the cert's common name as being pulp's identity

    :param cert_pem: PEM encoded client certificate sent with the request
    :type  cert_pem: string
    '''

    cert = certificate.create_from_pem(cert_pem)
    cn = cert.subject()['CN']

    return cn == IDENTITY_CN
