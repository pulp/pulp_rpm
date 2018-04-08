from logging import getLogger

from pulpcore.plugin.models import Content, Remote, Publisher


log = getLogger(__name__)


class RpmContent(Content):
    """
    The "rpm" content type.

    Description of the content type.

    Fields:
        field1 (type): Description of the field1
        field2 (type): Description of the field2
        ...

    """
    TYPE = 'type'

    # field1 = models.TextField(blank=False, null=False)
    # field2 = models.TextField(blank=False, null=False)

    # class Meta:
    #     unique_together = (
    #         'field1',
    #         'field2'
    #     )


class RpmRemote(Remote):
    """
    Remote for "rpm" content.
    """
    TYPE = 'rpm'


class RpmPublisher(Publisher):
    """
    Publisher for "rpm" content.
    """
    TYPE = 'rpm'
