from gettext import gettext as _
from rest_framework import serializers

from pulpcore.plugin.serializers import AlternateContentSourceSerializer
from pulp_rpm.app.models import RpmAlternateContentSource


class RpmAlternateContentSourceSerializer(AlternateContentSourceSerializer):
    """
    Serializer for RPM alternate content source.
    """

    def validate_paths(self, paths):
        """Validate that paths do not start with /."""
        for path in paths:
            if path.startswith("/"):
                raise serializers.ValidationError(_("Path cannot start with a slash."))
            if not path.endswith("/"):
                raise serializers.ValidationError(_("Path must end with a slash."))
        return paths

    class Meta:
        fields = AlternateContentSourceSerializer.Meta.fields
        model = RpmAlternateContentSource
