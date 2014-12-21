import unittest

from .distributors.iso_distributor.distributor_mocks import get_basic_config
from pulp_rpm.plugins import configuration_utils


class TestValidateNonRequiredBool(unittest.TestCase):
    """
    Assert correct behavior from the _validate_required_bool() function.
    """

    def test_bool_not_set(self):
        """
        If the bool is not set, it should be cool.
        """
        config = get_basic_config()

        # This should not raise an Exception, since the setting is not required
        configuration_utils.validate_non_required_bool(config, 'setting_name')

    def test_bool_not_valid(self):
        """
        If the bool is not valid, it should return an error.
        """
        config = get_basic_config(**{'setting_name': 'Not true or false.'})

        try:
            configuration_utils.validate_non_required_bool(config, 'setting_name')
            self.fail('The validation should have failed, but it did not.')
        except configuration_utils.ValidationError, e:
            self.assertEqual(str(e),
                             'The configuration parameter <setting_name> may only be set to a '
                             'boolean value, but is currently set to <Not true or false.>.')

    def test_bool_valid(self):
        """
        If the bool is valid, it should return successfully.
        """
        config = get_basic_config(**{'setting_name': 'false'})

        # This should not raise an Exception
        configuration_utils.validate_non_required_bool(config, 'setting_name')
