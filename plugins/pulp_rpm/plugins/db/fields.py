from mongoengine import StringField
from pulp.plugins.util import verification


class ChecksumTypeStringField(StringField):

    def validate(self, value):
        """
        Validates that value is a checksumtype known to pulp platform

        :param value: The value to validate
        :type  value: basestring

        :return: None
        """
        super(ChecksumTypeStringField, self).validate(value)
        verification.sanitize_checksum_type(value)
