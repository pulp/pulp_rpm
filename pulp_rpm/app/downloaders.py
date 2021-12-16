import os

from aiohttp_xmlrpc.client import ServerProxy, _Method
from logging import getLogger
from lxml import etree
from urllib.parse import quote, unquote, urlparse

from pulpcore.plugin.download import FileDownloader, HttpDownloader
from pulp_rpm.app.exceptions import UlnCredentialsError
from pulp_rpm.app.shared_utils import urlpath_sanitize


log = getLogger(__name__)


class RpmFileDownloader(FileDownloader):
    """
    FileDownloader that strips out RPM's custom http downloader arguments.

    This is unfortunate, but there isn't currently a good pattern for customizing the downloader
    factory machinery such that certain types of arguments only apply to certain downloaders,
    so passing a kwarg into get_downloader() will pass it to constructor for any downloader.

    TODO: https://pulp.plan.io/issues/7352
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the downloader.
        """
        kwargs.pop("silence_errors_for_response_status_codes", None)
        super().__init__(*args, **kwargs)


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

    def __init__(
        self,
        *args,
        silence_errors_for_response_status_codes=None,
        sles_auth_token=None,
        urlencode=True,
        **kwargs,
    ):
        """
        Initialize the downloader.
        """
        self.sles_auth_token = sles_auth_token

        if silence_errors_for_response_status_codes is None:
            silence_errors_for_response_status_codes = set()
        self.silence_errors_for_response_status_codes = silence_errors_for_response_status_codes

        super().__init__(*args, **kwargs)

        new_url = self.url
        if urlencode:
            # Some upstream-repos (eg, Amazon) require url-encoded paths for things like "libc++"
            # Let's make them happy.
            # We can't urlencode the whole url, because BasicAuth is still A Thing and we would
            #   break username/passwords in the url.
            # So we need to urlencode **only the path** and **nothing else** .
            # We can't use _replace() and urlunparse(), because urlunparse() "helpfully" undoes
            #   the urlencode we just did in the path.
            # We can't use urljoin(), because urljoin() "helpfully" treats a number of schemes
            #  (like, say, uln:) as "can't take relative paths", and throws away everything
            #  **except** the path-portion
            # So, we have a pretty ugly workaround.
            parsed = urlparse(self.url)
            # two pieces of the URL: pre- and post-path
            (before_path, after_path) = self.url.split(parsed.path)
            new_path = quote(unquote(parsed.path), safe=":/")  # fix the path
            new_url = "{}{}{}".format(before_path, new_path, after_path)  # rebuild
        if self.sles_auth_token:
            auth_param = f"?{self.sles_auth_token}"
            self.url = urlpath_sanitize(new_url) + auth_param
        else:
            self.url = new_url

    def raise_for_status(self, response):
        """
        Raise error if aiohttp response status is >= 400 and not silenced.

        Raises:
            FileNotFoundError: If aiohttp response status is 403 or 404 and silenced.
            aiohttp.ClientResponseError: If the response status is 400 or higher and not silenced.
        """
        silenced = response.status in self.silence_errors_for_response_status_codes

        if not silenced:
            response.raise_for_status()

        if response.status in (404, 403):
            raise FileNotFoundError()

    async def _run(self, extra_data=None):
        """
        Download, validate, and compute digests on the `url`. This is a coroutine.

        This method provides the same return object type and documented in
        :meth:`~pulpcore.plugin.download.BaseDownloader._run`.
        """
        async with self.session.get(
            self.url, proxy=self.proxy, proxy_auth=self.proxy_auth, auth=self.auth
        ) as response:
            self.raise_for_status(response)
            to_return = await self._handle_response(response)
            await response.release()
            self.response_headers = response.headers

        if self._close_session_on_finalize:
            self.session.close()
        return to_return


class UlnDownloader(RpmDownloader):
    """
    Custom Downloader for ULN repositories.

    Args:
        username (str): Username for authentication in ULN network
        password (str): password for authentication in ULN network
        uln_server_base_url (str): ULN server url.

    Raises:
        UlnCredentialsError: If no or not valid ULN credentials are given,
            this Error will be displayed
    """

    def __init__(self, *args, username=None, password=None, uln_server_base_url=None, **kwargs):
        """
        Initialize the downloader for ULN repositories.

        If no server URL is given, use the server url from oracle linux.
        """
        self.username = username
        self.password = password
        self.uln_server_base_url = uln_server_base_url
        self.headers = None
        self.session_key = None

        super().__init__(*args, **kwargs)

    async def _run(self, extra_data=None):
        """
        Download, validate, and compute digests on the `url`. This is a coroutine.

        Once per session the coroutine logs into the ULN account using the
        ULN username and password. The returned key is used for authentification
        for all other downloads.

        This method provides the same return object type and documented in
        :meth:`~pulpcore.plugin.download.BaseDownloader._run`.
        """
        parsed = urlparse(self.url)

        if parsed.scheme == "uln":
            # get ULN Session-key
            SERVER_URL = os.path.join(self.uln_server_base_url, "rpc/api")

            # set proxy for authentification
            client = AllowProxyServerProxy(
                SERVER_URL, proxy=self.proxy, proxy_auth=self.proxy_auth, auth=self.auth
            )
            if not self.session_key:
                self.session_key = await client.auth.login(self.username, self.password)
                if len(self.session_key) != 43:
                    raise UlnCredentialsError("No valid ULN credentials given.")
                self.headers = {"X-ULN-API-User-Key": self.session_key}
                await client.close()
            # build request url from input uri
            channelLabel = parsed.netloc
            path = parsed.path.lstrip("/")
            url = os.path.join(self.uln_server_base_url, "XMLRPC/GET-REQ", channelLabel, path)
        async with self.session.get(
            url, proxy=self.proxy, proxy_auth=self.proxy_auth, auth=self.auth, headers=self.headers
        ) as response:
            self.raise_for_status(response)
            to_return = await self._handle_response(response)
            await response.release()
            self.response_headers = response.headers

        if self._close_session_on_finalize:
            self.session.close()
            client.close()
        return to_return


class AllowProxyServerProxy(ServerProxy):
    """
    Overwriting the class aiohttp_xmlrpc.ServreProxy to allow proxy handling.

    Until aiohttp-xmlrpc allows http post with proxy, use this patch.
    This only works for http connection to the proxy, https connections are not supported!
    """

    def __init__(self, *args, proxy, proxy_auth, auth, **kwargs):
        """
        Initialisation with proxy.
        """
        self.__proxy = proxy
        self.__proxy_auth = proxy_auth
        self.__auth = auth
        super().__init__(*args, **kwargs)

    async def __remote_call(self, method_name, *args, **kwargs):
        """
        Set proxy for HTTP POST call.
        """
        async with self.client.post(
            str(self.url),
            data=etree.tostring(
                self._make_request(method_name, *args, **kwargs),
                xml_declaration=True,
                encoding=self.encoding,
            ),
            headers=self.headers,
            proxy=self.__proxy,
            proxy_auth=self.__proxy_auth,
            auth=self.__auth,
        ) as response:
            response.raise_for_status()

            return self._parse_response((await response.read()), method_name)

    # we also have to overwrite this method, because '__'-method-names are only valid
    # in the class they are defined in, therefore only overwriting __remote_call() does not work!
    def __getattr__(self, method_name):
        """
        Dynamically create method for attribute.

        Copied from aiohttp-xmlrpc/aiohttp_xmlrpc/client.py
        """
        # Trick to keep the "close" method available
        if method_name == "close":
            return self.__close
        else:
            # Magic method dispatcher
            return _Method(self.__remote_call, method_name)

    def __close(self):
        return self.client.close()
