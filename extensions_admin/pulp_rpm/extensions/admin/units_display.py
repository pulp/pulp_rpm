from pulp_rpm.common.ids import (TYPE_ID_RPM, TYPE_ID_SRPM, TYPE_ID_DRPM, TYPE_ID_ERRATA,
                                 TYPE_ID_DISTRO, TYPE_ID_PKG_GROUP, TYPE_ID_PKG_CATEGORY,
                                 TYPE_ID_PKG_ENVIRONMENT, TYPE_ID_YUM_REPO_METADATA_FILE)


def get_formatter_for_type(type_id):
    """
    Return a method that takes one argument (a unit) and formats a short string
    to be used as the output for the unit_remove command

    :param type_id: The type of the unit for which a formatter is needed
    :type type_id: str
    """
    type_formatters = {
        TYPE_ID_RPM: _details_package,
        TYPE_ID_SRPM: _details_package,
        TYPE_ID_DRPM: _details_drpm,
        TYPE_ID_ERRATA: lambda x: x.get('id'),
        TYPE_ID_DISTRO: lambda x: x.get('id'),
        TYPE_ID_PKG_GROUP: lambda x: x.get('id'),
        TYPE_ID_PKG_CATEGORY: lambda x: x.get('id'),
        TYPE_ID_PKG_ENVIRONMENT: lambda x: x.get('id'),
        TYPE_ID_YUM_REPO_METADATA_FILE: _yum_repo_metadata_name_only,
    }
    return type_formatters[type_id]


def _details_package(package):
    """
    A formatter that prints detailed package information.

    The package argument is expected to contain keys 'name', 'version', 'release', and 'arch';
    each key is expected to contain strings as their corresponding values. The formatter
    concatenates those values with dashes as follows:

        name-version-release-arch

    This is a detailed package formatter that can be used with different unit types.

    :param package: The package to have its formatting returned.
    :type package: dict
    :return: The display string of the package
    :rtype: str
    """
    return '%s-%s-%s-%s' % (package['name'], package['version'], package['release'],
                            package['arch'])


def _details_drpm(drpm):
    """
    A formatter that prints simple drpm information.

    The drpm argument is expected to contain the key 'filename', and is expected to have a string
    as the corresponding value. The formatter returns the value of 'filename' as the formatted
    string to use. This is a simple package formatter that should be used with drpm unit types.

    :param drpm: The drpm to have its formatting returned.
    :type drpm: dict
    :return: The display string of the drpm
    :rtype: str
    """
    return drpm['filename']


def _yum_repo_metadata_name_only(unit):
    """
    A formatter for yum repo metadata units.

    Yum repo metadata units do not come with much information. The most meaningful is the
    data_type, which identifies the type of metadata. The unit argument is expected to contain the
    key 'data_type', and is expected to have a string as the corresponding value. This formatter
    returns the value stored with the key 'data_type' as the string representation for the unit.

    :param unit: The unit to have its formatting returned.
    :type unit: dict
    :return: The display string of the unit
    :rtype: str
    """
    return unit['data_type']
