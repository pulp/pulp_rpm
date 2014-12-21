import unittest

from pulp.plugins.config import PluginCallConfiguration

from pulp_rpm.plugins.distributors.export_distributor import export_utils
from pulp_rpm.common import constants


class TestIsValidPrefix(unittest.TestCase):
    """
    Tests that is_valid_prefix only returns true for strings containing alphanumeric characters,
    dashes, and underscores.
    """

    def test_invalid_prefix(self):
        self.assertFalse(export_utils.is_valid_prefix('prefix#with*special@chars'))

    def test_valid_prefix(self):
        self.assertTrue(export_utils.is_valid_prefix('No-special_chars1'))


class TestValidateExportConfig(unittest.TestCase):
    """
    Tests for validate_export_config in export_utils
    """

    def setUp(self):
        self.repo_config = {
            constants.PUBLISH_HTTPS_KEYWORD: True,
            constants.PUBLISH_HTTP_KEYWORD: False,
        }
        self.valid_config = PluginCallConfiguration({}, self.repo_config)

    def test_missing_required_key(self):
        # Confirm missing required keys causes validation to fail
        result, msg = export_utils.validate_export_config(PluginCallConfiguration({}, {}))
        self.assertFalse(result)

    def test_required_keys_only(self):
        # Confirm providing only required keys causes a successful validation
        return_value = export_utils.validate_export_config(self.valid_config)
        self.assertEqual(return_value, (True, None))

    def test_non_bool_http_key(self):
        # Confirm including a non-boolean for the publish http keyword fails validation
        self.repo_config[constants.PUBLISH_HTTP_KEYWORD] = 'potato'
        result, msg = export_utils.validate_export_config(
            PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result)

    def test_non_bool_https_key(self):
        # Confirm including a non-boolean for the publish https keyword fails validation
        self.repo_config[constants.PUBLISH_HTTPS_KEYWORD] = 'potato'
        result, msg = export_utils.validate_export_config(
            PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result)

    def test_invalid_key(self):
        self.repo_config['leek'] = 'garlic'
        result, msg = export_utils.validate_export_config(
            PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result)

    def test_full_config(self):
        self.repo_config[constants.SKIP_KEYWORD] = []
        self.repo_config[constants.ISO_PREFIX_KEYWORD] = 'prefix'
        self.repo_config[constants.ISO_SIZE_KEYWORD] = 630
        self.repo_config[constants.EXPORT_DIRECTORY_KEYWORD] = '/path/to/dir'
        self.repo_config[constants.START_DATE_KEYWORD] = '2013-07-18T11:22:00'
        self.repo_config[constants.END_DATE_KEYWORD] = '2013-07-18T11:23:00'

        result, msg = export_utils.validate_export_config(
            PluginCallConfiguration({}, self.repo_config))
        self.assertTrue(result)

    def test_bad_skip_config(self):
        # Setup
        self.repo_config[constants.SKIP_KEYWORD] = 'not a list'

        # Test that a skip list that isn't a list fails to validate
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_bad_prefix_config(self):
        # Setup
        self.repo_config[constants.ISO_PREFIX_KEYWORD] = '!@#$%^&'

        # Test that a prefix with invalid characters fails validation
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_bad_iso_size_config(self):
        # Setup
        self.repo_config[constants.ISO_SIZE_KEYWORD] = -55

        # Test that a prefix with invalid characters fails validation
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_bad_start_date(self):
        # Setup
        self.repo_config[constants.START_DATE_KEYWORD] = 'malformed date'

        # Test
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_bad_end_date(self):
        # Setup
        self.repo_config[constants.END_DATE_KEYWORD] = 'malformed date'

        # Test
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_non_absolute_path(self):
        # Setup
        self.repo_config[constants.EXPORT_DIRECTORY_KEYWORD] = 'non/absolute/path'

        # Test that if the export directory isn't found, validation fails
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_none_path(self):
        # Setup
        self.repo_config[constants.EXPORT_DIRECTORY_KEYWORD] = None

        # Test
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_none_skip(self):
        # Setup
        self.repo_config[constants.SKIP_KEYWORD] = None

        # Test
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_none_iso_prefix(self):
        # Setup
        self.repo_config[constants.ISO_PREFIX_KEYWORD] = None

        # Test
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_none_iso_size(self):
        # Setup
        self.repo_config[constants.ISO_SIZE_KEYWORD] = None

        # Test
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_none_start_date(self):
        # Setup
        self.repo_config[constants.START_DATE_KEYWORD] = None

        # Test
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_none_end_date(self):
        # Setup
        self.repo_config[constants.END_DATE_KEYWORD] = None

        # Test
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_none_http(self):
        # Setup
        self.repo_config[constants.PUBLISH_HTTP_KEYWORD] = None

        # Test
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])

    def test_none_https(self):
        # Setup
        self.repo_config[constants.PUBLISH_HTTPS_KEYWORD] = None

        # Test
        result = export_utils.validate_export_config(PluginCallConfiguration({}, self.repo_config))
        self.assertFalse(result[0])


class TestCreateDateRangeFilter(unittest.TestCase):
    """
    Tests for the create_date_range_filter method in export_utils
    """

    def setUp(self):
        self.repo_config = {
            constants.PUBLISH_HTTPS_KEYWORD: True,
            constants.PUBLISH_HTTP_KEYWORD: False,
        }
        self.test_date = '2010-01-01 12:00:00'

    def test_no_filter(self):
        # Test calling create_date_range_filter with no dates in the configuration
        date = export_utils.create_date_range_filter(PluginCallConfiguration({}, self.repo_config))
        self.assertTrue(date is None)

    def test_start_date_only(self):
        # Set up a configuration with a start date, and the expected return
        self.repo_config[constants.START_DATE_KEYWORD] = self.test_date
        config = PluginCallConfiguration({}, self.repo_config)
        expected_filter = {export_utils.ASSOCIATED_UNIT_DATE_KEYWORD: {'$gte': self.test_date}}

        # Test
        date_filter = export_utils.create_date_range_filter(config)
        self.assertEqual(expected_filter, date_filter)

    def test_end_date_only(self):
        # Set up a configuration with an end date, and the expected return
        self.repo_config[constants.END_DATE_KEYWORD] = self.test_date
        config = PluginCallConfiguration({}, self.repo_config)
        expected_filter = {export_utils.ASSOCIATED_UNIT_DATE_KEYWORD: {'$lte': self.test_date}}

        # Test
        date_filter = export_utils.create_date_range_filter(config)
        self.assertEqual(expected_filter, date_filter)

    def test_start_and_end_date(self):
        # Set up a configuration with both a start date and an end date.
        self.repo_config[constants.START_DATE_KEYWORD] = self.test_date
        self.repo_config[constants.END_DATE_KEYWORD] = self.test_date
        config = PluginCallConfiguration({}, self.repo_config)
        expected_filter = {export_utils.ASSOCIATED_UNIT_DATE_KEYWORD: {'$gte': self.test_date,
                                                                       '$lte': self.test_date}}

        # Test
        date_filter = export_utils.create_date_range_filter(config)
        self.assertEqual(expected_filter, date_filter)
