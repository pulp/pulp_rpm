from pulpcore.plugin.serializers import ContentSerializer, ImporterSerializer, PublisherSerializer

from .models import RpmContent, RpmImporter, RpmPublisher


class RpmContentSerializer(ContentSerializer):
    """
    A Serializer for RpmContent.

    Add serializers for the new fields defined in RpmContent and
    add those fields to the Meta class keeping fields from the parent class as well.
    Provide help_text.

    For example::

    field1 = serializers.TextField(help_text="field1 description")
    field2 = serializers.IntegerField(help_text="field2 description")
    field3 = serializers.CharField(help_text="field3 description")

    class Meta:
        fields = ContentSerializer.Meta.fields + ('field1', 'field2', 'field3')
        model = RpmContent
    """

    class Meta:
        fields = ContentSerializer.Meta.fields
        model = RpmContent


class RpmImporterSerializer(ImporterSerializer):
    """
    A Serializer for RpmImporter.

    Add any new fields if defined on RpmImporter.
    Similar to the example above, in RpmContentSerializer.
    Additional validators can be added to the parent validators list

    For example::

    class Meta:
        validators = ImporterSerializer.Meta.validators + [myValidator1, myValidator2]
    """

    class Meta:
        fields = ImporterSerializer.Meta.fields
        model = RpmImporter


class RpmPublisherSerializer(PublisherSerializer):
    """
    A Serializer for RpmPublisher.

    Add any new fields if defined on RpmPublisher.
    Similar to the example above, in RpmContentSerializer.
    Additional validators can be added to the parent validators list

    For example::

    class Meta:
        validators = PublisherSerializer.Meta.validators + [myValidator1, myValidator2]
    """

    class Meta:
        fields = PublisherSerializer.Meta.fields
        model = RpmPublisher
