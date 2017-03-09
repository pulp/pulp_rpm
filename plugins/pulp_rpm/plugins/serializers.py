import gzip

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

    def serialize(self, unit):
        """
        Convert a single unit to it's dictionary form.

        Decompress values of the `repodata` dict field for RPM/SRPM units.

        :param instance: The object to be converted
        :type instance: object
        """
        for metadata_type in unit.get('repodata', {}):
            metadata = unit['repodata'][metadata_type]
            unit['repodata'][metadata_type] = gzip.zlib.decompress(metadata)
        return super(RpmBase, self).serialize(unit)


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


class PackageLangpacks(platform_serializers.ModelSerializer):
    """
    Serializer for a PackageLangpacks models
    """
    class Meta:
        remapped_fields = {}


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
