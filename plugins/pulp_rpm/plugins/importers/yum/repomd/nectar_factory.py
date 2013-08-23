# -*- coding: utf-8 -*-
# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

"""
Contains logic surrounding which nectar downloader implementation to use.
"""

import urlparse

from nectar.downloaders.curl import HTTPCurlDownloader
from nectar.downloaders.threaded import HTTPThreadedDownloader


# Mapping from scheme string to downloader class to instantiate
SCHEME_DOWNLOADERS = {
    'file'  : HTTPCurlDownloader,
    'http'  : HTTPThreadedDownloader,
    'https' : HTTPThreadedDownloader,
}


def create_downloader(repo_url, nectar_config, event_listener):
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
        raise ValueError('Unsupported scheme: %s' % parsed.scheme)

    return SCHEME_DOWNLOADERS[parsed.scheme](nectar_config, event_listener=event_listener)

