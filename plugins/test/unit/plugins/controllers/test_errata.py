import copy

import mock

from mongoengine import NotUniqueError

from pulp.common.compat import unittest

from pulp_rpm.plugins.controllers import errata as errata_controller
from pulp_rpm.plugins.db import models


class TestCreateOrUpdatePkglist(unittest.TestCase):
    def setUp(self):
        self.existing_packages = [
            {'src': 'pulp-test-package-0.3.1-1.fc22.src.rpm',
             'name': 'pulp-test-package',
             'arch': 'x86_64',
             'sums': 'sums',
             'filename': 'pulp-test-package-0.3.1-1.fc22.x86_64.rpm',
             'epoch': '0',
             'version': '0.3.1',
             'release': '1.fc22',
             'type': 'sha256'}]
        self.collection = {
            'packages': self.existing_packages,
            'name': 'test-name',
            'short': ''}

    @mock.patch('pulp_rpm.plugins.db.models.ErratumPkglist.save')
    @mock.patch('pulp_rpm.plugins.db.models.ErratumPkglist.objects')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.objects')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.update_needed')
    def test_merge_pkglists_same_repo_newer(self, mock_update_needed, mock_errata_obj,
                                            mock_pkglist_obj, mock_save):
        """
        Assert that the existing pkglist is overwritten, if the uploaded erratum is newer than
        the existing one.
        """
        existing_collection = copy.deepcopy(self.collection)
        uploaded_collection = copy.deepcopy(self.collection)
        uploaded_collection['packages'][0]['version'] = '2.0'

        existing_pkglist_data = {'errata_id': 'some erratum',
                                 'collections': [existing_collection]}
        uploaded_erratum_data = {'errata_id': 'some erratum',
                                 'pkglist': [uploaded_collection]}
        existing_pkglist = models.ErratumPkglist(**existing_pkglist_data)
        uploaded_erratum = models.Errata(**uploaded_erratum_data)
        mock_pkglist_obj.filter.return_value.first.return_value = existing_pkglist
        mock_update_needed.return_value = True
        mock_save.side_effect = [NotUniqueError, None]

        errata_controller.create_or_update_pkglist(uploaded_erratum, 'my_repo')

        # make sure the existing collection is changed
        self.assertEqual(existing_pkglist.collections[0]['packages'][0]['version'],
                         uploaded_collection['packages'][0]['version'])

        # make sure save() is called twice since existing pkglist was updated
        self.assertEqual(mock_save.call_count, 2)

        # make sure pkglist on the Erratum model is empty
        self.assertEqual(uploaded_erratum.pkglist, [])

    @mock.patch('pulp_rpm.plugins.db.models.ErratumPkglist.save')
    @mock.patch('pulp_rpm.plugins.db.models.ErratumPkglist.objects')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.objects')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.update_needed')
    def test_merge_pkglists_same_repo_older(self, mock_update_needed, mock_errata_obj,
                                            mock_pkglist_obj, mock_save):
        """
        Assert that the existing pkglist is untouched, if the uploaded erratum is older than
        the existing one.
        """
        existing_collection = copy.deepcopy(self.collection)
        uploaded_collection = copy.deepcopy(self.collection)
        uploaded_collection['packages'][0]['version'] = '2.0'

        existing_pkglist_data = {'errata_id': 'some erratum',
                                 'collections': [existing_collection]}
        uploaded_erratum_data = {'errata_id': 'some erratum',
                                 'pkglist': [uploaded_collection]}
        existing_pkglist = models.ErratumPkglist(**existing_pkglist_data)
        uploaded_erratum = models.Errata(**uploaded_erratum_data)
        mock_pkglist_obj.filter.return_value.first.return_value = existing_pkglist
        mock_errata_obj.filter.return_value.first.return_value = models.Errata()
        mock_update_needed.return_value = False
        mock_save.side_effect = NotUniqueError

        errata_controller.create_or_update_pkglist(uploaded_erratum, 'my_repo')

        # make sure save() is called once since existing pkglist is untouched
        self.assertEqual(mock_save.call_count, 1)

        # make sure pkglist on the Erratum model is empty anyway
        self.assertEqual(uploaded_erratum.pkglist, [])

    @mock.patch('pulp_rpm.plugins.db.models.ErratumPkglist.save')
    @mock.patch('pulp_rpm.plugins.db.models.ErratumPkglist.objects')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.objects')
    @mock.patch('pulp_rpm.plugins.db.models.Errata.update_needed')
    def test_new_pkglist(self, mock_update_needed, mock_errata_obj,
                         mock_pkglist_obj, mock_save):
        """
        Assert that new pkglist is created if there is no existing one.
        """
        uploaded_collection = copy.deepcopy(self.collection)
        uploaded_erratum_data = {'errata_id': 'some erratum',
                                 'pkglist': [uploaded_collection]}
        uploaded_erratum = models.Errata(**uploaded_erratum_data)

        errata_controller.create_or_update_pkglist(uploaded_erratum, 'my_repo')

        # make sure save() is called once
        self.assertEqual(mock_save.call_count, 1)

        # make sure pkglist on the Erratum model is empty
        self.assertEqual(uploaded_erratum.pkglist, [])
