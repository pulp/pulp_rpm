import os
import shutil
import tempfile
import unittest

from pulp.common.constants import DEFAULT_CA_PATH
from pulp.common.lock import Lock

from pulp_rpm.handlers import repolib
from pulp_rpm.handlers.repo_file import MirrorListFile, RepoFile, Repo


CACERT = 'MY-CA-CERTIFICATE'
CLIENTCERT = 'MY-CLIENT-KEY-AND-CERTIFICATE'

REPO_ID = 'repo-1'
REPO_NAME = 'Repository 1'

ENABLED = True


class TestRepolib(unittest.TestCase):
    def setUp(self):
        self.working_dir = tempfile.mkdtemp()
        self.TEST_REPO_FILENAME = os.path.join(self.working_dir, 'TestRepolibFile.repo')
        self.TEST_MIRROR_LIST_FILENAME = os.path.join(self.working_dir,
                                                      'TestRepolibFile.mirrorlist')
        self.TEST_KEYS_DIR = os.path.join(self.working_dir, 'TestRepolibFile-keys')
        self.TEST_CERT_DIR = os.path.join(self.working_dir, 'TestRepolibFile-certificates')
        self._LOCK_FILE = os.path.join(self.working_dir, 'test_repolib_lock.pid')
        self.LOCK = Lock(self._LOCK_FILE)

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def test_bind_new_file(self):
        """
        Tests binding a repo when the underlying .repo file does not exist.
        """
        url_list = ['http://pulpserver']

        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, {}, CLIENTCERT, ENABLED, self.LOCK)

        self.assertTrue(os.path.exists(self.TEST_REPO_FILENAME))
        self.assertTrue(not os.path.exists(self.TEST_MIRROR_LIST_FILENAME))
        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()

        self.assertEqual(1, len(repo_file.all_repos()))

        loaded = repo_file.get_repo(REPO_ID)
        self.assertTrue(loaded is not None)
        self.assertEqual(loaded['name'], REPO_NAME)
        self.assertTrue(loaded['enabled'])
        self.assertEqual(loaded['gpgcheck'], '0')
        self.assertEqual(loaded['gpgkey'], None)

        self.assertEqual(loaded['baseurl'], url_list[0])
        self.assertTrue('mirrorlist' not in loaded)

        path = loaded['sslclientcert']
        f = open(path)
        content = f.read()
        f.close()
        self.assertEqual(CLIENTCERT, content)
        # verify_ssl defaults to True
        self.assertTrue(loaded['sslverify'], '1')
        self.assertEqual(loaded['sslcacert'], DEFAULT_CA_PATH)

    def test_bind_ssl_verify_false(self):
        """
        Tests binding a repo with verify_ssl set explicitly to False.
        """
        url_list = ['http://pulpserver']

        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, {}, CLIENTCERT, ENABLED, self.LOCK,
                     verify_ssl=False)

        self.assertTrue(os.path.exists(self.TEST_REPO_FILENAME))
        self.assertTrue(not os.path.exists(self.TEST_MIRROR_LIST_FILENAME))
        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()

        self.assertEqual(1, len(repo_file.all_repos()))

        loaded = repo_file.get_repo(REPO_ID)
        self.assertTrue(loaded is not None)
        self.assertEqual(loaded['name'], REPO_NAME)
        self.assertTrue(loaded['enabled'])
        self.assertEqual(loaded['gpgcheck'], '0')
        self.assertEqual(loaded['gpgkey'], None)

        self.assertEqual(loaded['baseurl'], url_list[0])
        self.assertTrue('mirrorlist' not in loaded)

        path = loaded['sslclientcert']
        f = open(path)
        content = f.read()
        f.close()
        self.assertEqual(CLIENTCERT, content)
        self.assertTrue(loaded['sslverify'], '0')
        # No CA path should have been used
        self.assertEqual(loaded['sslcacert'], None)

    def test_bind_ssl_verify_true_default_ca_path(self):
        """
        Tests binding a repo with verify_ssl set explicitly to True and the default ca_path.
        """
        url_list = ['http://pulpserver']

        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, {}, CLIENTCERT, ENABLED, self.LOCK,
                     verify_ssl=True)

        self.assertTrue(os.path.exists(self.TEST_REPO_FILENAME))
        self.assertTrue(not os.path.exists(self.TEST_MIRROR_LIST_FILENAME))
        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()

        self.assertEqual(1, len(repo_file.all_repos()))

        loaded = repo_file.get_repo(REPO_ID)
        self.assertTrue(loaded is not None)
        self.assertEqual(loaded['name'], REPO_NAME)
        self.assertTrue(loaded['enabled'])
        self.assertEqual(loaded['gpgcheck'], '0')
        self.assertEqual(loaded['gpgkey'], None)

        self.assertEqual(loaded['baseurl'], url_list[0])
        self.assertTrue('mirrorlist' not in loaded)

        path = loaded['sslclientcert']
        f = open(path)
        content = f.read()
        f.close()
        self.assertEqual(CLIENTCERT, content)
        self.assertTrue(loaded['sslverify'], '1')
        # The default CA path should have been used
        self.assertEqual(loaded['sslcacert'], DEFAULT_CA_PATH)

    def test_bind_ssl_verify_true_explicit_ca_path(self):
        """
        Tests binding a repo with verify_ssl set explicitly to True and an explicit ca_path.
        """
        url_list = ['http://pulpserver']
        ca_path = '/some/path'

        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, {}, CLIENTCERT, ENABLED, self.LOCK,
                     verify_ssl=True,
                     ca_path=ca_path)

        self.assertTrue(os.path.exists(self.TEST_REPO_FILENAME))
        self.assertTrue(not os.path.exists(self.TEST_MIRROR_LIST_FILENAME))
        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()

        self.assertEqual(1, len(repo_file.all_repos()))

        loaded = repo_file.get_repo(REPO_ID)
        self.assertTrue(loaded is not None)
        self.assertEqual(loaded['name'], REPO_NAME)
        self.assertTrue(loaded['enabled'])
        self.assertEqual(loaded['gpgcheck'], '0')
        self.assertEqual(loaded['gpgkey'], None)

        self.assertEqual(loaded['baseurl'], url_list[0])
        self.assertTrue('mirrorlist' not in loaded)

        path = loaded['sslclientcert']
        f = open(path)
        content = f.read()
        f.close()
        self.assertEqual(CLIENTCERT, content)
        self.assertTrue(loaded['sslverify'], '1')
        # The default CA path should have been used
        self.assertEqual(loaded['sslcacert'], ca_path)

    def test_bind_existing_file(self):
        """
        Tests binding a new repo when the underlying file exists and has repos in it
        (the existing repo shouldn't be deleted).
        """

        # Setup
        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.add_repo(Repo('existing-repo-1'))
        repo_file.save()

        # Test
        url_list = ['http://pulpserver']
        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, {}, None, ENABLED, self.LOCK)

        # Verify
        self.assertTrue(os.path.exists(self.TEST_REPO_FILENAME))

        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()

        self.assertEqual(2, len(repo_file.all_repos()))

    def test_bind_update_repo(self):
        """
        Tests calling bind on an existing repo with new repo data. The host URL and key data
        remain unchanged.
        """
        url_list = ['http://pulp1', 'http://pulp2']
        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, None, None, ENABLED, self.LOCK)
        updated_name = 'Updated'

        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, updated_name, None, None, None, ENABLED, self.LOCK)

        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()
        loaded = repo_file.get_repo(REPO_ID)
        self.assertEqual(loaded['name'], updated_name)

    def test_bind_update_host_urls(self):
        """
        Tests calling bind on an existing repo with new repo data. This test will test
        the more complex case where a mirror list existed in the original repo but is
        not necessary in the updated repo.
        """
        url_list = ['http://pulp1', 'http://pulp2']
        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, None, None, ENABLED, self.LOCK)
        self.assertTrue(os.path.exists(self.TEST_MIRROR_LIST_FILENAME))

        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, None, ['http://pulpx'], None, None, ENABLED, self.LOCK)

        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()
        loaded = repo_file.get_repo(REPO_ID)
        self.assertEqual(loaded['baseurl'], 'http://pulpx')
        self.assertTrue(not os.path.exists(self.TEST_MIRROR_LIST_FILENAME))

    def test_bind_host_urls_one_to_many(self):
        """
        Tests that changing from a single URL to many properly updates the baseurl and
        mirrorlist entries of the repo.
        """
        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, ['https://pulpx'], None, None, ENABLED, self.LOCK)
        url_list = ['http://pulp1', 'http://pulp2']

        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, None, None, ENABLED, self.LOCK)

        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()

        loaded = repo_file.get_repo(REPO_ID)
        self.assertTrue('baseurl' not in loaded)
        self.assertTrue('mirrorlist' in loaded)

    def test_bind_host_urls_many_to_one(self):
        """
        Tests that changing from multiple URLs (mirrorlist usage) to a single URL
        properly sets the repo metadata.
        """
        # Setup
        url_list = ['http://pulp1', 'http://pulp2']
        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, None, None, ENABLED, self.LOCK)

        # Test
        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, ['http://pulpx'], None, None, ENABLED, self.LOCK)

        # Verify
        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()

        loaded = repo_file.get_repo(REPO_ID)
        self.assertTrue('baseurl' in loaded)
        self.assertTrue('mirrorlist' not in loaded)

    def test_bind_update_keys(self):
        """
        Tests changing the GPG keys on a previously bound repo.
        """
        keys = {'key1': 'KEY1', 'key2': 'KEY2'}
        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, ['http://pulp'], keys, None, ENABLED, self.LOCK)
        new_keys = {'key1': 'KEYX'}

        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, None, None, new_keys, None, ENABLED, self.LOCK)

        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()

        loaded = repo_file.get_repo(REPO_ID)
        self.assertEqual(loaded['gpgcheck'], '1')
        self.assertEqual(1, len(loaded['gpgkey'].split('\n')))
        self.assertEqual(1, len(os.listdir(os.path.join(self.TEST_KEYS_DIR, REPO_ID))))

        key_file = open(loaded['gpgkey'].split('\n')[0][5:], 'r')
        contents = key_file.read()
        key_file.close()

        self.assertEqual(contents, 'KEYX')

    def test_bind_update_remove_keys(self):
        """
        Tests that updating a previously bound repo by removing its keys correctly
        configures the repo and deletes the key files.
        """
        keys = {'key1': 'KEY1', 'key2': 'KEY2'}
        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, ['http://pulp'], keys, None, ENABLED, self.LOCK)

        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, None, None, {}, None, ENABLED, self.LOCK)

        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()
        loaded = repo_file.get_repo(REPO_ID)
        self.assertEqual(loaded['gpgcheck'], '0')
        self.assertEqual(loaded['gpgkey'], None)
        self.assertTrue(not os.path.exists(os.path.join(self.TEST_KEYS_DIR, REPO_ID)))

    def test_clear_ca_path(self):
        repolib.bind(
            self.TEST_REPO_FILENAME,
            self.TEST_MIRROR_LIST_FILENAME,
            self.TEST_KEYS_DIR,
            self.TEST_CERT_DIR,
            REPO_ID,
            REPO_NAME,
            ['http://pulp'],
            [],
            CLIENTCERT,
            ENABLED,
            self.LOCK,
            verify_ssl=True,
            ca_path='/some/path')

        repolib.bind(
            self.TEST_REPO_FILENAME,
            self.TEST_MIRROR_LIST_FILENAME,
            self.TEST_KEYS_DIR,
            self.TEST_CERT_DIR,
            REPO_ID,
            REPO_NAME,
            ['http://pulp'],
            [],
            CLIENTCERT,
            ENABLED,
            self.LOCK)

        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()
        loaded = repo_file.get_repo(REPO_ID)
        certdir = os.path.join(self.TEST_CERT_DIR, REPO_ID)
        self.assertTrue(len(os.listdir(certdir)), 1)
        path = loaded['sslclientcert']
        f = open(path)
        content = f.read()
        f.close()
        self.assertEqual(CLIENTCERT, content)
        self.assertTrue(loaded['sslverify'], '0')

    def test_clear_clientcert(self):
        # setup
        repolib.bind(
            self.TEST_REPO_FILENAME,
            self.TEST_MIRROR_LIST_FILENAME,
            self.TEST_KEYS_DIR,
            self.TEST_CERT_DIR,
            REPO_ID,
            REPO_NAME,
            ['http://pulp'],
            [],
            CLIENTCERT,
            ENABLED,
            self.LOCK)
        repolib.bind(
            self.TEST_REPO_FILENAME,
            self.TEST_MIRROR_LIST_FILENAME,
            self.TEST_KEYS_DIR,
            self.TEST_CERT_DIR,
            REPO_ID,
            REPO_NAME,
            ['http://pulp'],
            [],
            None,
            ENABLED,
            self.LOCK,
            verify_ssl=True)
        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()
        loaded = repo_file.get_repo(REPO_ID)
        certdir = os.path.join(self.TEST_CERT_DIR, REPO_ID)
        self.assertFalse(os.path.exists(certdir))
        self.assertTrue(loaded['sslverify'], '1')

    def test_update_ca_path(self):
        NEW_PATH = '/new/path/'
        repolib.bind(
            self.TEST_REPO_FILENAME,
            self.TEST_MIRROR_LIST_FILENAME,
            self.TEST_KEYS_DIR,
            self.TEST_CERT_DIR,
            REPO_ID,
            REPO_NAME,
            ['http://pulp'],
            [],
            CLIENTCERT,
            ENABLED,
            self.LOCK,
            verify_ssl=True,
            ca_path='/some/path/')

        repolib.bind(
            self.TEST_REPO_FILENAME,
            self.TEST_MIRROR_LIST_FILENAME,
            self.TEST_KEYS_DIR,
            self.TEST_CERT_DIR,
            REPO_ID,
            REPO_NAME,
            ['http://pulp'],
            [],
            CLIENTCERT,
            ENABLED,
            self.LOCK,
            verify_ssl=True,
            ca_path=NEW_PATH)

        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()
        loaded = repo_file.get_repo(REPO_ID)
        certdir = os.path.join(self.TEST_CERT_DIR, REPO_ID)
        self.assertTrue(len(os.listdir(certdir)), 1)
        path = loaded['sslcacert']
        self.assertEqual(path, NEW_PATH)
        path = loaded['sslclientcert']
        f = open(path)
        content = f.read()
        f.close()
        self.assertEqual(CLIENTCERT, content)
        self.assertTrue(loaded['sslverify'], '1')

    def test_update_clientcert(self):
        NEWCLIENTCRT = 'THE-NEW-CLIENT-CERT'
        repolib.bind(
            self.TEST_REPO_FILENAME,
            self.TEST_MIRROR_LIST_FILENAME,
            self.TEST_KEYS_DIR,
            self.TEST_CERT_DIR,
            REPO_ID,
            REPO_NAME,
            ['http://pulp'],
            [],
            CLIENTCERT,
            ENABLED,
            self.LOCK)

        repolib.bind(
            self.TEST_REPO_FILENAME,
            self.TEST_MIRROR_LIST_FILENAME,
            self.TEST_KEYS_DIR,
            self.TEST_CERT_DIR,
            REPO_ID,
            REPO_NAME,
            ['http://pulp'],
            [],
            NEWCLIENTCRT,
            ENABLED,
            self.LOCK)

        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()
        loaded = repo_file.get_repo(REPO_ID)
        certdir = os.path.join(self.TEST_CERT_DIR, REPO_ID)
        self.assertTrue(len(os.listdir(certdir)), 1)
        path = loaded['sslclientcert']
        f = open(path)
        content = f.read()
        f.close()
        self.assertEqual(NEWCLIENTCRT, content)
        self.assertTrue(loaded['sslverify'], '1')

    def test_bind_single_url(self):
        """
        Tests that binding with a single URL will produce a baseurl in the repo.
        """
        url_list = ['http://pulpserver']

        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, {}, None, ENABLED, self.LOCK)

        self.assertTrue(os.path.exists(self.TEST_REPO_FILENAME))
        self.assertTrue(not os.path.exists(self.TEST_MIRROR_LIST_FILENAME))
        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()
        loaded = repo_file.get_repo(REPO_ID)
        self.assertEqual(loaded['baseurl'], url_list[0])
        self.assertTrue('mirrorlist' not in loaded)

    def test_bind_multiple_url(self):
        """
        Tests that binding with a list of URLs will produce a mirror list and the
        correct mirrorlist entry in the repo entry.
        """
        url_list = ['http://pulpserver', 'http://otherserver']

        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, {}, None, ENABLED, self.LOCK)

        self.assertTrue(os.path.exists(self.TEST_REPO_FILENAME))
        self.assertTrue(os.path.exists(self.TEST_MIRROR_LIST_FILENAME))
        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()
        loaded = repo_file.get_repo(REPO_ID)
        self.assertTrue('baseurl' not in loaded)
        self.assertEqual(loaded['mirrorlist'], 'file:' + self.TEST_MIRROR_LIST_FILENAME)
        mirror_list_file = MirrorListFile(self.TEST_MIRROR_LIST_FILENAME)
        mirror_list_file.load()
        self.assertEqual(mirror_list_file.entries[0], 'http://pulpserver')
        self.assertEqual(mirror_list_file.entries[1], 'http://otherserver')

    def test_bind_multiple_keys(self):
        """
        Tests that binding with multiple key URLs correctly stores the repo entry.
        """
        url_list = ['http://pulpserver']
        keys = {'key1': 'KEY1', 'key2': 'KEY2'}

        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, keys, None, ENABLED, self.LOCK)

        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()
        loaded = repo_file.get_repo(REPO_ID)
        self.assertEqual(loaded['gpgcheck'], '1')
        self.assertEqual(2, len(loaded['gpgkey'].split('\n')))
        self.assertEqual(2, len(os.listdir(os.path.join(self.TEST_KEYS_DIR, REPO_ID))))

    def test_unbind_repo_exists(self):
        """
        Tests the normal case of unbinding a repo that exists in the repo file.
        """

        # Setup
        repoid = 'test-unbind-repo'
        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.add_repo(Repo(repoid))
        repo_file.save()

        # Test
        repolib.unbind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                       self.TEST_CERT_DIR,
                       'test-unbind-repo', self.LOCK)

        # verify
        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load(
            allow_missing=False)  # the file should still be there, so error if it doesn't

        self.assertEqual(0, len(repo_file.all_repos()))

        certdir = os.path.join(self.TEST_CERT_DIR, repoid)
        self.assertFalse(os.path.exists(certdir))

    def test_unbind_repo_with_mirrorlist(self):
        """
        Tests that unbinding a repo that had a mirror list deletes the mirror list
        file.
        """
        url_list = ['http://pulp1', 'http://pulp2', 'http://pulp3']
        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, {}, None, ENABLED, self.LOCK)
        self.assertTrue(os.path.exists(self.TEST_MIRROR_LIST_FILENAME))

        repolib.unbind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                       self.TEST_CERT_DIR,
                       REPO_ID, self.LOCK)

        repo_file = RepoFile(self.TEST_REPO_FILENAME)
        repo_file.load()
        self.assertEqual(0, len(repo_file.all_repos()))
        self.assertTrue(not os.path.exists(self.TEST_MIRROR_LIST_FILENAME))

    def test_unbind_repo_with_keys(self):
        """
        Tests that unbinding a repo that had GPG keys deletes the key files.
        """
        url_list = ['http://pulp1']
        keys = {'key1': 'KEY1', 'key2': 'KEY2'}
        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, url_list, keys, None, ENABLED, self.LOCK)
        self.assertTrue(os.path.exists(os.path.join(self.TEST_KEYS_DIR, REPO_ID)))

        repolib.unbind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                       self.TEST_CERT_DIR,
                       REPO_ID, self.LOCK)

        self.assertTrue(not os.path.exists(os.path.join(self.TEST_KEYS_DIR, REPO_ID)))

    def test_unbind_missing_file(self):
        """
        Tests that calling unbind in the case where the underlying .repo file has been
        deleted does not result in an error.
        """

        # Setup
        self.assertTrue(not os.path.exists(self.TEST_REPO_FILENAME))

        # Test
        repolib.unbind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                       self.TEST_CERT_DIR,
                       REPO_ID, self.LOCK)

        # Verify
        # The above shouldn't throw an error

    def test_unbind_missing_repo(self):
        """
        Tests that calling unbind on a repo that isn't bound does not result in
        an error.
        """
        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, ['http://pulp'], {}, None, ENABLED, self.LOCK)

        # This shouldn't throw an error; the net effect is still that the repo is unbound. This test
        # just makes sure this runs without error, which is why there are no assertions.
        repolib.unbind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                       self.TEST_CERT_DIR,
                       'fake-repo', self.LOCK)

    def test_delete_repo_file(self):
        """
        Tests that calling delete_repo_file deletes the repo file.
        """
        repolib.bind(self.TEST_REPO_FILENAME, self.TEST_MIRROR_LIST_FILENAME, self.TEST_KEYS_DIR,
                     self.TEST_CERT_DIR,
                     REPO_ID, REPO_NAME, ['http://pulp'], {}, None, ENABLED, self.LOCK)
        self.assertTrue(os.path.exists(self.TEST_REPO_FILENAME))

        repolib.delete_repo_file(self.TEST_REPO_FILENAME, self.LOCK)

        self.assertFalse(os.path.exists(self.TEST_REPO_FILENAME))
