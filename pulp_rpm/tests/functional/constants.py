# coding=utf-8
from types import MappingProxyType
from urllib.parse import urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL
from pulp_smash.pulp3.constants import (
    BASE_PUBLISHER_PATH,
    BASE_REMOTE_PATH,
    CONTENT_PATH
)


RPM_CONTENT_PATH = urljoin(CONTENT_PATH, 'rpm/rpms/')
SRPM_CONTENT_PATH = urljoin(CONTENT_PATH, 'rpm/srpms/')

RPM_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'rpm/')
RPM_PUBLISHER_PATH = urljoin(BASE_PUBLISHER_PATH, 'rpm/')


RPM_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm/')
RPM_FIXTURE_COUNT = 35
RPM_URL = urljoin(RPM_FIXTURE_URL, 'bear-4.1-1.noarch.rpm')

SRPM_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'srpm/')
SRPM_FIXTURE_COUNT = 3
SRPM_URL = urljoin(RPM_FIXTURE_URL, 'test-srpm01-1.0-1.src.rpm')

RPM_DATA = MappingProxyType({
    'name': 'bear',
    'epoch': '0',
    'version': '4.1',
    'release': '1',
    'arch': 'noarch',
    'metadata': {
        'release': '1',
        'license': 'GPLv2',
        'description': 'A dummy package of bear',
        'files': {'dir': [], 'file': ['/tmp/bear.txt']},
        'group': 'Internet/Applications',
        'size': {'installed': 42, 'package': 1846},
        'sourcerpm': 'bear-4.1-1.src.rpm',
        'summary': 'A dummy package of bear',
        'vendor': None,
    },
})
"""Metadata for an RPM with an associated erratum.
The metadata tags that may be present in an RPM may be printed with:
.. code-block:: sh
    rpm --querytags
Metadata for an RPM can be printed with a command like the following:
.. code-block:: sh
    for tag in name epoch version release arch vendor; do
        echo "$(rpm -qp bear-4.1-1.noarch.rpm --qf "%{$tag}")"
    done
There are three ways to measure the size of an RPM:
installed size
    The size of all the regular files in the payload.
archive size
    The uncompressed size of the payload, including necessary CPIO headers.
package size
    The actual size of an RPM file, as returned by ``stat --format='%s' …``.
For more information, see the Fedora documentation on `RPM headers
<https://docs.fedoraproject.org/en-US/Fedora_Draft_Documentation/0.1/html/RPM_Guide/ch-package-structure.html#id623000>`_.
"""

RPM = '{}-{}{}-{}.{}.rpm'.format(
    RPM_DATA['name'],
    RPM_DATA['epoch'] + '!' if RPM_DATA['epoch'] != '0' else '',
    RPM_DATA['version'],
    RPM_DATA['release'],
    RPM_DATA['arch'],
)
"""The name of an RPM file. See :data:`pulp_smash.constants.RPM_SIGNED_URL`."""

RPM_SIGNED_FIXTURE_COUNT = 32
"""The number of packages available at :data:`RPM_SIGNED_FIXTURE_URL`."""

RPM_SIGNED_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'rpm-signed/')
"""The URL to a signed RPM repository. See :data:`RPM_SIGNED_URL`."""

RPM_SIGNED_URL = urljoin(RPM_SIGNED_FIXTURE_URL, RPM)
"""The URL to an RPM file.
Built from :data:`RPM_SIGNED_FIXTURE_URL` and :data:`RPM`.
"""
