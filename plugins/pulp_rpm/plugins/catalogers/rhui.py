import urllib2

from urllib2 import ProxyHandler
from base64 import urlsafe_b64encode
from logging import getLogger

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.catalogers.yum import YumCataloger


log = getLogger(__name__)


TYPE_ID = 'rhui'

ID_DOC_HEADER = "X-RHUI-ID"
ID_SIG_HEADER = "X-RHUI-SIGNATURE"
ID_DOC_URL = "http://169.254.169.254/latest/dynamic/instance-identity/document"
ID_SIG_URL = "http://169.254.169.254/latest/dynamic/instance-identity/signature"


def entry_point():
    """
    The Pulp platform uses this method to load the cataloger.
    :return: RHUICataloger class and an (empty) config
    :rtype:  tuple
    """
    return RHUICataloger, {}


class RHUICataloger(YumCataloger):

    @staticmethod
    def _load_id():
        """
        Loads and returns the Amazon metadata for identifying the instance.
        :return the AMI ID.
        :rtype str
        """
        try:
            opener = urllib2.build_opener(ProxyHandler({}))
            fp = opener.open(ID_DOC_URL)
            document = fp.read()
            fp.close()
            return document
        except urllib2.URLError, e:
            log.error('Load amazon ID document failed: %s', str(e))

    @staticmethod
    def _load_signature():
        """
        Loads and returns the Amazon signature of hte Amazon identification metadata.
        :return the signature.
        :rtype str
        """
        try:
            opener = urllib2.build_opener(ProxyHandler({}))
            fp = opener.open(ID_SIG_URL)
            signature = fp.read()
            fp.close()
            return signature
        except urllib2.URLError, e:
            log.error('Load amazon signature failed: %s', str(e))

    @classmethod
    def metadata(cls):
        return {
            'id': TYPE_ID,
            'display_name': "RHUI Cataloger",
            'types': [models.RPM.TYPE]
        }

    def downloader(self, conduit, config, url):
        """
        Get object suitable for downloading content published
        in the content catalog by a content source.
        :param conduit: Access to pulp platform API.
        :type conduit: pulp.server.plugins.conduits.cataloger.CatalogerConduit
        :param config: The content source configuration.
        :type config: dict
        :param url: The URL for the content source.
        :type url: str
        """
        document = RHUICataloger._load_id()
        signature = RHUICataloger._load_signature()
        downloader = super(RHUICataloger, self).downloader(conduit, conduit, url)
        downloader.config[ID_DOC_HEADER] = urlsafe_b64encode(document)
        downloader.config[ID_SIG_HEADER] = urlsafe_b64encode(signature)
        return downloader
