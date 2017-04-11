# -*- coding: utf-8 -*-

"""
Contains logic surrounding which nectar downloader implementation to use.
"""

import urlparse

from gettext import gettext as _

from nectar.downloaders.local import LocalFileDownloader
from nectar.downloaders.threaded import HTTPThreadedDownloader


# Mapping from scheme string to downloader class to instantiate
SCHEME_DOWNLOADERS = {
    'file': LocalFileDownloader,
    'http': HTTPThreadedDownloader,
    'https': HTTPThreadedDownloader,
}


def create_downloader(repo_url, nectar_config, event_listener=None):
    """
    Returns an appropriate downloader instance for the given repository location.

    Note: In the future we may want to enhance this by passing in some sort of
    configuration that will let this method apply more than just protocol checking.

    :param repo_url:        where the repository will be syncced from
    :type  repo_url:        str
    :param nectar_config:   download config to be used by nectar
    :type  nectar_config:   nectar.config.DownloaderConfig
    :param event_listener:  listener that will receive reports of download completion
    :type  event_listener:  nectar.listener.DownloadEventListener

    :return:    a new nectar downloader instance
    :rtype:     nectar.downloaders.base.Downloader
    """
    parsed = urlparse.urlparse(repo_url)

    if parsed.scheme not in SCHEME_DOWNLOADERS:
        supported = '|'.join(SCHEME_DOWNLOADERS.keys())
        raise ValueError(
            _('Invalid feed URL - scheme must be: ({s})').format(
                s=supported))

    return SCHEME_DOWNLOADERS[parsed.scheme](nectar_config, event_listener=event_listener)
