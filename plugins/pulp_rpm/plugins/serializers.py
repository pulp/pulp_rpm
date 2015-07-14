from pulp.server.webservices.views import serializers as platform_serializers


class Distribution(platform_serializers.ModelSerializer):
    """
    Serializer for a RpmBase based models
    """
    class Meta:
        remapped_fields = {'distribution_id': 'id',
                           'user_metadata': 'pulp_user_metadata'}


class Drpm(platform_serializers.ModelSerializer):
    """
    Serializer for a RpmBase based models
    """
    class Meta:
        remapped_fields = {'file_name': 'filename',
                           'checksum_type': 'checksumtype',
                           'old_epoch': 'oldepoch',
                           'old_version': 'oldversion',
                           'old_release': 'oldrelease',
                           'user_metadata': 'pulp_user_metadata'}


class RpmBase(platform_serializers.ModelSerializer):
    """
    Serializer for a RpmBase based models
    """
    class Meta:
        remapped_fields = {'checksum_type': 'checksumtype',
                           'file_name': 'filename',
                           'relative_path': 'relativepath',
                           'source_rpm': 'sourcerpm',
                           'user_metadata': 'pulp_user_metadata'}


class Errata(platform_serializers.ModelSerializer):
    """
    Serializer for a Errata models
    """
    class Meta:
        remapped_fields = {'errata_from': 'from',
                           'errata_id': 'id',
                           'user_metadata': 'pulp_user_metadata'}


class PackageGroup(platform_serializers.ModelSerializer):
    """
    Serializer for a PackageGroup models
    """
    class Meta:
        remapped_fields = {'package_group_id': 'id',
                           'user_metadata': 'pulp_user_metadata'}


class PackageCategory(platform_serializers.ModelSerializer):
    """
    Serializer for a PackageCategory models
    """
    class Meta:
        remapped_fields = {'package_category_id': 'id',
                           'group_ids': 'packagegroupids',
                           'user_metadata': 'pulp_user_metadata'}


class PackageEnvironment(platform_serializers.ModelSerializer):
    """
    Serializer for a PackageEnvironment models
    """
    class Meta:
        remapped_fields = {'package_environment_id': 'id',
                           'user_metadata': 'pulp_user_metadata'}


class YumMetadataFile(platform_serializers.ModelSerializer):
    """
    Serializer for a YumMetadataFile models
    """
    class Meta:
        remapped_fields = {'user_metadata': 'pulp_user_metadata'}


class ISO(platform_serializers.ModelSerializer):
    """
    Serializer for a ISO models
    """
    class Meta:
        remapped_fields = {'user_metadata': 'pulp_user_metadata'}
