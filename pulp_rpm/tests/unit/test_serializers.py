import pytest

from pulp_rpm.app.serializers.distribution import AddonSerializer, VariantSerializer


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
