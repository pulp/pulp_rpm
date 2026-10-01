import json
import urllib.parse
from unittest.mock import MagicMock

import pytest

from pulp_rpm.app.serializers.distribution import AddonSerializer, VariantSerializer
from pulp_rpm.app.serializers.repository import OsvConfigField

_CONFIG = {"ecosystem": "rpm", "repo": "myrepo"}


@pytest.mark.parametrize(
    "labels,expected",
    [
        ({}, None),
        ({"osv.rpm.config": urllib.parse.quote(json.dumps(_CONFIG))}, _CONFIG),
        ({"osv.rpm.config": json.dumps(_CONFIG)}, _CONFIG),
        ({"osv.rpm.config": "not-json"}, None),
    ],
)
def test_osv_config_field_get_attribute(labels, expected):
    rpm_repository_instance = MagicMock()
    rpm_repository_instance.pulp_labels = labels
    assert OsvConfigField().get_attribute(rpm_repository_instance) == expected


@pytest.mark.parametrize(
    "serializer, data, field",
    [
        (
            AddonSerializer,
            {
                "addon_id": "../outside",
                "uid": "addon",
                "name": "Addon",
                "type": "addon",
                "packages": "Packages",
            },
            "addon_id",
        ),
        (
            VariantSerializer,
            {
                "variant_id": "../outside",
                "uid": "variant",
                "name": "Variant",
                "type": "variant",
                "packages": "Packages",
            },
            "variant_id",
        ),
    ],
)
def test_subrepo_serializer_rejects_unsafe_id(serializer, data, field):
    """Addon and variant IDs cannot escape a publication directory."""
    serialized = serializer(data=data)

    assert not serialized.is_valid()
    assert field in serialized.errors
