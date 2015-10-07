from pulp.server.webservices.views import serializers as platform_serializers


class Distribution(platform_serializers.ModelSerializer):
    """
    Serializer for Distribution based models
    """
    class Meta:
        remapped_fields = {'distribution_id': 'id'}


class Drpm(platform_serializers.ModelSerializer):
    """
    Serializer for Drpm based models
    """
    class Meta:
        remapped_fields = {}


class RpmBase(platform_serializers.ModelSerializer):
    """
    Serializer for RpmBase based models
    """
    class Meta:
        remapped_fields = {}


class Errata(platform_serializers.ModelSerializer):
    """
    Serializer for Errata models
    """
    class Meta:
        remapped_fields = {'errata_from': 'from',
                           'errata_id': 'id'}


class PackageGroup(platform_serializers.ModelSerializer):
    """
    Serializer for a PackageGroup models
    """
    class Meta:
        remapped_fields = {'package_group_id': 'id'}


class PackageCategory(platform_serializers.ModelSerializer):
    """
    Serializer for a PackageCategory models
    """
    class Meta:
        remapped_fields = {'package_category_id': 'id'}


class PackageEnvironment(platform_serializers.ModelSerializer):
    """
    Serializer for a PackageEnvironment models
    """
    class Meta:
        remapped_fields = {'package_environment_id': 'id'}


class YumMetadataFile(platform_serializers.ModelSerializer):
    """
    Serializer for a YumMetadataFile models
    """
    class Meta:
        remapped_fields = {}


class ISO(platform_serializers.ModelSerializer):
    """
    Serializer for a ISO models
    """
    class Meta:
        remapped_fields = {}
