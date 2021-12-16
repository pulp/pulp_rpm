import aiohttp_xmlrpc
import asyncio
import asynctest
import os

from pulp_rpm.app.downloaders import UlnDownloader, UlnCredentialsError


class TestUlnDownloader(asynctest.TestCase):
    """
    Test for Download of ULN repositories.

    This test checks that for a ULN uri, the authentification key for ULN login
    is passed on in the headers correctly.
    """

    def setUp(self):
        """
        Setup method for TestUlnDownloader class.
        """
        self.my_loop = asyncio.new_event_loop()
        self.addCleanup(self.my_loop.close)

    def init_UlnDownloader(
        self,
        url,
        session=None,
        auth=None,
        proxy=None,
        proxy_auth=None,
        headers_ready_callback=None,
        headers=None,
        username=None,
        password=None,
        uln_server_base_url="https://linux-update.oracle.com/",
        **kwargs,
    ):
        """
        Initialize the UlnDownloader object.
        """
        downloader = UlnDownloader(
            url,
            session=session,
            username=username,
            password=password,
            uln_server_base_url=uln_server_base_url,
            **kwargs,
        )
        return downloader

    async def run_downloader(self, url, session, username, password):
        """
        Initialize and run a UlnDownloader object.
        """
        self.downloader = self.init_UlnDownloader(
            url=url,
            session=session,
            username=username,
            password=password,
        )
        await self.downloader.run()

    async def mock_auth_login(self, username, password):
        """
        Mock the authentification on the ULN server.

        Return a key with exactly 43 digits if and only if
        the username and password are correct.
        """
        self.assertEqual(username, "penguins")
        self.assertEqual(password, "iamabirdbutcannotfly")
        return "this_is_my_magic_key_with_exactly_43_digits"

    async def mock_failed_auth_login(self, username, password):
        """
        Mock a failed authentification at the ULN server.
        """
        return None

    def create_Future(self, *args):
        """
        Make the Mock objects awaitable.
        """
        f = asyncio.Future()
        f.set_result(None)
        return f

    @asynctest.patch.object(aiohttp_xmlrpc.client._Method, "__getattr__")
    @asynctest.patch("aiohttp.ClientSession")
    def test_valid_auth(self, mock_session, mock_getattr):
        """
        Test a valid authentification and download process for ULN.
        """
        mock_getattr.return_value = self.mock_auth_login
        mock_response = mock_session.get().__aenter__.return_value
        mock_response.content.read.side_effect = self.create_Future
        mock_response.release.side_effect = self.create_Future

        self.my_loop.run_until_complete(
            self.run_downloader(
                "uln://channelLabel/repodata/repomd.xml",
                mock_session,
                "penguins",
                "iamabirdbutcannotfly",
            )
        )

        # make test assertions
        # assert that the session key was imported correctly
        uln_auth_url = "https://linux-update.oracle.com/rpc/api"
        repomd_url = (
            "https://linux-update.oracle.com/XMLRPC/GET-REQ/channelLabel/repodata/repomd.xml"
        )
        self.assertEqual(uln_auth_url, os.path.join(self.downloader.uln_server_base_url, "rpc/api"))
        # what really happens is the _Method-instance 'auth' has it's method 'login' called.
        mock_getattr.assert_called_once_with("login")
        self.assertEqual(
            self.downloader.headers,
            {"X-ULN-API-User-Key": "this_is_my_magic_key_with_exactly_43_digits"},
        )
        # assert that the session request is called correctly
        mock_session.get.assert_called_with(
            repomd_url,
            proxy=self.downloader.proxy,
            proxy_auth=self.downloader.proxy_auth,
            auth=self.downloader.auth,
            headers=self.downloader.headers,
        )

        @asynctest.patch.object(aiohttp_xmlrpc.client._Method, "__getattr__")
        @asynctest.patch("aiohttp.ClientSession")
        def test_invalid_auth(self, mock_session, mock_getattr):
            """
            Test a invalid authentification for ULN.

            Authentification can fail for wrong credentials or for unsuccsessful
            authentification.
            """
            mock_getattr.return_value = self.mock_failed_auth_login

            mock_response = mock_session.get().__aenter__.return_value
            mock_response.content.read.side_effect = self.create_Future
            mock_response.release.side_effect = self.create_Future

            # assert error for wrong credentials
            with self.assertRaises(UlnCredentialsError):
                self.my_loop.run_until_complete(
                    self.run_downloader(
                        "uln://channelLabel/repodata/repomd.xml", mock_session, "penguins", None
                    )
                )

            # failed authentification error
            with self.assertRaises(UlnCredentialsError):
                self.my_loop.run_until_complete(
                    self.run_downloader(
                        "uln://channelLabel/repodata/repomd.xml",
                        mock_session,
                        "penguins",
                        "iamabirdbutcannotfly",
                    )
                )

    def tearDown(self):
        """
        Tear Down of Uln Test.
        """
        self.my_loop.close()
