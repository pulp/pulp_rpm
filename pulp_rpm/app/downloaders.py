from logging import getLogger
from urllib.parse import urljoin

from pulpcore.plugin.download import HttpDownloader


log = getLogger(__name__)


class RpmDownloader(HttpDownloader):
    """
    Custom Downloader that automatically handles authentication token for SLES repositories.

    Args:
        silence_errors_for_response_status_codes (iterable): An iterable of response exception
            codes to be ignored when raising exception. e.g. `{404}`
        sles_auth_token (str): SLES authentication token.

    Raises:
        FileNotFoundError: If aiohttp response status is 404 and silenced.

    """

    def __init__(self, *args, silence_errors_for_response_status_codes=set(), sles_auth_token=None,
                 **kwargs):
        """
        Initialize the downloader.
        """
        self.sles_auth_token = sles_auth_token
        self.silence_errors_for_response_status_codes = silence_errors_for_response_status_codes

        super().__init__(*args, **kwargs)

    def raise_for_status(self, response):
        """
        Raise error if aiohttp response status is >= 400 and not silenced.

        Raises:
            FileNotFoundError: If aiohttp response status is 404 and silenced.
            aiohttp.ClientResponseError: If the response status is 400 or higher and not silenced.

        """
        silenced = response.status in self.silence_errors_for_response_status_codes

        if not silenced:
            response.raise_for_status()

        if response.status == 404:
            raise FileNotFoundError()

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
            self.raise_for_status(response)
            to_return = await self._handle_response(response)
            await response.release()
            self.response_headers = response.headers

        if self._close_session_on_finalize:
            self.session.close()
        return to_return
