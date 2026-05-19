import json
import urllib.parse
from unittest.mock import MagicMock

import pytest

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
