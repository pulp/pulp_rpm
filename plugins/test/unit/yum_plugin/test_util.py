# -*- coding: utf-8 -*-

import mock
import os
import shutil
import tempfile
import unittest

from pulp_rpm.devel import rpm_support_base
from pulp_rpm.yum_plugin import util


class TestUtil(rpm_support_base.PulpRPMTests):
    def setUp(self):
        super(TestUtil, self).setUp()
        self.init()

    def tearDown(self):
        super(TestUtil, self).tearDown()
        self.clean()

    def init(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                                     "../../../../pulp_rpm/test/unit/server/data"))

    def clean(self):
        shutil.rmtree(self.temp_dir)

    def test_is_rpm_newer(self):
        rpm_a = {"name": "rpm_test_name", "epoch": "0", "release": "el6.1", "version": "2",
                 "arch": "noarch"}
        newer_a = {"name": "rpm_test_name", "epoch": "0", "release": "el6.1", "version": "3",
                   "arch": "noarch"}
        newer_a_diff_arch = {"name": "rpm_test_name", "epoch": "0", "release": "el6.1",
                             "version": "2", "arch": "i386"}
        rpm_b = {"name": "rpm_test_name_B", "epoch": "0", "release": "el6.1", "version": "5",
                 "arch": "noarch"}

        self.assertTrue(util.is_rpm_newer(newer_a, rpm_a))
        self.assertFalse(util.is_rpm_newer(newer_a_diff_arch, rpm_a))
        self.assertFalse(util.is_rpm_newer(rpm_a, newer_a))
        self.assertFalse(util.is_rpm_newer(newer_a, rpm_b))


class TestGenerateListingFiles(unittest.TestCase):
    def test_repo_dir_not_descendant(self):
        self.assertRaises(ValueError, util.generate_listing_files, '/a/b/c', '/d/e/f')

    def test_all(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            # setup a directory structure and define the expected listing file values
            publish_dir = os.path.join(tmp_dir, 'a/b/c')
            os.makedirs(publish_dir)
            os.makedirs(os.path.join(tmp_dir, 'a/d'))
            os.makedirs(os.path.join(tmp_dir, 'a/b/e'))
            expected = ['a', 'b\nd', 'c\ne']

            # run it
            util.generate_listing_files(tmp_dir, publish_dir)

            # ensure that each listing file exists and has the correct contents
            current_path = tmp_dir
            for next_dir, expected_listing in zip(['a', 'b', 'c'], expected):
                file_path = os.path.join(current_path, 'listing')
                with open(file_path) as open_file:
                    self.assertEqual(open_file.read(), expected_listing)
                current_path = os.path.join(current_path, next_dir)

            # make sure there is not a listing file inside the repo's publish dir
            self.assertFalse(os.path.exists(os.path.join(publish_dir, 'listing')))

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class SignerTest(rpm_support_base.PulpRPMTests):

    def setUp(self):
        super(SignerTest, self).setUp()
        self.test_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.test_dir, ignore_errors=True)

        signme = ('#!/bin/bash -e\n'
                  'echo $0\n'
                  'echo GPG_KEYID=$GPG_KEYID\n'
                  'echo GPG_REPOSITORY_NAME=$GPG_REPOSITORY_NAME\n'
                  'echo GPG_DIST\n'
                  'exit 0\n'
                  )
        self.sign_cmd = self.mkfile("signme", contents=signme)
        os.chmod(self.sign_cmd, 0o755)
        self.key_id = '8675309'
        self.repository_name = 'jenny'
        self.dist = 'tutone'

    def mkfile(self, path, contents=None):
        if contents is None:
            contents = "\n"
        fpath = os.path.join(self.test_dir, path)
        if isinstance(contents, unicode):
            mode = 'w'
        else:
            mode = 'wb'
        with open(fpath, mode) as fh:
            fh.write(contents)
        return fpath

    @mock.patch("pulp_rpm.yum_plugin.util.tempfile.NamedTemporaryFile")
    @mock.patch("pulp_rpm.yum_plugin.util.subprocess.Popen")
    def test_sign(self, _Popen, _NamedTemporaryFile):
        filename = self.mkfile("Random_File", contents="Name: Random_File")
        kwargs = dict(dist=self.dist, repository_name=self.repository_name)
        so = util.SignOptions(cmd=self.sign_cmd, key_id=self.key_id, **kwargs)

        _Popen.return_value.wait.return_value = 0
        signer = util.Signer(options=so)
        signer.sign(filename)

        _Popen.assert_called_once_with(
            [self.sign_cmd, filename],
            env=dict(
                GPG_CMD=self.sign_cmd,
                GPG_KEY_ID=self.key_id,
                GPG_REPOSITORY_NAME=self.repository_name,
                GPG_DIST=self.dist,
            ),
            stdout=_NamedTemporaryFile.return_value,
            stderr=_NamedTemporaryFile.return_value,
        )

    @mock.patch("pulp_rpm.yum_plugin.util.tempfile.NamedTemporaryFile")
    @mock.patch("pulp_rpm.yum_plugin.util.subprocess.Popen")
    def test_sign_error(self, _Popen, _NamedTemporaryFile):
        filename = self.mkfile("Release", contents="Name: Release")
        so = util.SignOptions(cmd=self.sign_cmd)

        _Popen.return_value.wait.return_value = 2
        signer = util.Signer(options=so)
        with self.assertRaises(util.SignerError) as ctx:
            signer.sign(filename)
        self.assertEquals(
            _NamedTemporaryFile.return_value,
            ctx.exception.stdout)
        self.assertEquals(
            _NamedTemporaryFile.return_value,
            ctx.exception.stderr)

    def test_bad_signing_options(self):
        bad_so = "SoWhat"
        with self.assertRaises(ValueError) as ctx:
            util.Signer(options=bad_so)
        self.assertTrue(
            str(ctx.exception).startswith('Signer options: unexpected type'))

    def test_raise_errors(self):
        err = dict(stdout='STDOUT', stderr='STDERR')
        msg = "Signer Error"
        with self.assertRaises(util.SignerError) as ctx:
            raise util.SignerError(msg, **err)
        self.assertTrue(msg in str(ctx.exception))
        self.assertEquals(ctx.exception.stdout, err['stdout'])
        self.assertEquals(ctx.exception.stderr, err['stderr'])
