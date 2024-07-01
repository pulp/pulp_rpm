"""drf-spectacular Extensions.

See:
https://drf-spectacular.readthedocs.io/en/latest/customization.html#step-5-extensions
"""

from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.plumbing import build_basic_type
from drf_spectacular.types import OpenApiTypes


class RestrictedJsonFieldExtension(OpenApiSerializerFieldExtension):
    """
    Workaround to makes drf JSONField to produce only Object Type.

    See:
    https://github.com/tfranzel/drf-spectacular/issues/1242
    """

    target_class = "rest_framework.fields.JSONField"
    # match_subclasses = True  # not needed here but good to know.

    def map_serializer_field(self, auto_schema, direction):
        return build_basic_type(OpenApiTypes.OBJECT)
