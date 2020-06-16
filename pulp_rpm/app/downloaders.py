from logging import getLogger
from urllib.parse import urljoin

from aiohttp.client_exceptions import ClientResponseError

from pulpcore.plugin.download import HttpDownloader


log = getLogger(__name__)


class RpmDownloader(HttpDownloader):
    """
    Custom Downloader that automatically handles authentication token for SLES repositories.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the downloader.
        """
        if 'sles_auth_token' in kwargs:
            self.sles_auth_token = kwargs.pop('sles_auth_token')
        else:
            self.sles_auth_token = None
        super().__init__(*args, **kwargs)

    async def _run(self, extra_data=None):
        """
        Download, validate, and compute digests on the `url`. This is a coroutine.

        This method provides the same return object type and documented in
        :meth:`~pulpcore.plugin.download.BaseDownloader._run`.

        """
        if self.sles_auth_token:
            auth_param = f'?{self.sles_auth_token}'
            url = urljoin(self.url, auth_param)
        else:
            url = self.url

        async with self.session.get(url) as response:
            try:
                response.raise_for_status()
            except ClientResponseError:
                raise
            to_return = await self._handle_response(response)
            await response.release()
            self.response_headers = response.headers

        if self._close_session_on_finalize:
            self.session.close()
        return to_return
