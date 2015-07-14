from logging import getLogger
from urllib2 import urlopen
from base64 import urlsafe_b64encode
from contextlib import closing

from pulp_rpm.common import ids
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.catalogers.yum import YumCataloger


log = getLogger(__name__)

TYPE_ID = 'rhui'

ID_DOC_HEADER = 'X-RHUI-ID'
ID_SIG_HEADER = 'X-RHUI-SIGNATURE'
ID_DOC_URL = 'http://169.254.169.254/latest/dynamic/instance-identity/document'
ID_SIG_URL = 'http://169.254.169.254/latest/dynamic/instance-identity/signature'


def entry_point():
    """
    The Pulp platform uses this method to load the cataloger.
    :return: RHUICataloger class and an (empty) config
    :rtype:  tuple
    """
    return RHUICataloger, {}


class RHUICataloger(YumCataloger):
    @classmethod
    def metadata(cls):
        return {
            'id': TYPE_ID,
            'display_name': "RHUI Cataloger",
            'types': [ids.TYPE_ID_RPM]
        }

    def nectar_config(self, config):
        """
        Get a nectar configuration using the specified content source configuration.
        :param config: The content source configuration.
        :type config: dict
        :return: A nectar downloader configuration
        :rtype: nectar.config.DownloaderConfig
        """
        nectar_config = super(RHUICataloger, self).nectar_config(config)
        with closing(urlopen(ID_DOC_URL)) as fp:
            amazon_id = fp.read()
        with closing(urlopen(ID_SIG_URL)) as fp:
            amazon_signature = fp.read()
        headers = nectar_config.headers or {}
        headers[ID_DOC_HEADER] = urlsafe_b64encode(amazon_id)
        headers[ID_SIG_HEADER] = urlsafe_b64encode(amazon_signature)
        nectar_config.headers = headers
        return nectar_config
