from mongoengine import StringField
from pulp.server import util


class ChecksumTypeStringField(StringField):

    def validate(self, value):
        """
        Validates that value is a checksumtype known to pulp platform

        :param value: The value to validate
        :type  value: basestring

        :return: None
        """
        super(ChecksumTypeStringField, self).validate(value)
        util.sanitize_checksum_type(value)
