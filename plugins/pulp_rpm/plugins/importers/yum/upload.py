import functools
import hashlib
import logging
import os
import stat
from xml.etree import cElementTree as ET

from pulp.plugins.loader import api as plugin_api
from pulp.plugins.util import verification
from pulp.server.controllers import repository as repo_controller
from pulp.server.exceptions import PulpCodedValidationException, PulpCodedException
from pulp.server.exceptions import error_codes as platform_errors
import rpm

from pulp_rpm.plugins.db import models
from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins.importers.yum import purge, utils
from pulp_rpm.plugins.importers.yum.parse import rpm as rpm_parse
from pulp_rpm.plugins.importers.yum.repomd import primary, group, packages


# this is required because some of the pre-migration XML tags use the "rpm"
# namespace, which causes a parse error if that namespace isn't declared.
FAKE_XML = '<?xml version="1.0" encoding="%(encoding)s"?><faketag ' \
           'xmlns:rpm="http://pulpproject.org">%(xml)s</faketag>'

# Used when extracting metadata from an RPM
RPMTAG_NOSOURCE = 1051
CHECKSUM_READ_BUFFER_SIZE = 65536

# Configuration option specified to not take the steps of linking a newly
# uploaded erratum with RPMs in the destination repository.
CONFIG_SKIP_ERRATUM_LINK = 'skip_erratum_link'

_LOGGER = logging.getLogger(__name__)


def update_fields_inbound(model_class, user_dict):
    """
    Rename keys in to map old API field names to new mongoengine names.

    This modifies the dictionary in place and returns None.

    :param model_class: The model class
    :type  model_class: subclass of pulp.server.db.model.ContentUnit

    :param user_dict: The dictionary to update in-place
    :type user_dict: dict

    :return: None
    """
    for new_name, old_name in model_class.SERIALIZER.Meta.remapped_fields.iteritems():
        if old_name in user_dict:
            user_dict[new_name] = user_dict[old_name]
            del user_dict[old_name]


# These are used by the _handle_* methods for each type so that the main driver
# method can consistently format/word the failure report. These should not be
# raised outside of this module.

class ModelInstantiationError(Exception):
    pass


class StoreFileError(Exception):
    pass


class PackageMetadataError(Exception):
    pass


def upload(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    :param repo: The repository to have the unit uploaded to
    :type  repo: pulp.server.db.model.Repository

    :param type_id: type of unit being uploaded
    :type  type_id: str

    :param unit_key: identifier for the unit, specified by the user; will likely be None
                     for RPM uploads as the data is extracted server-side
    :type  unit_key: dict or None

    :param metadata: any user-specified metadata for the unit; will likely be None
                     for RPM uploads as the data is extracted server-side
    :type  metadata: dict or None

    :param file_path: path on the Pulp server's filesystem to the temporary
           location of the uploaded file; may be None in the event that a
           unit is comprised entirely of metadata and has no bits associated
    :type  file_path: str

    :param conduit: provides access to relevant Pulp functionality
    :type  conduit: pulp.plugins.conduits.upload.UploadConduit

    :param config: plugin configuration for the repository
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :return: report of the details of the sync
    :rtype:  dict
    """
    handlers = {
        models.RPM._content_type_id.default: _handle_package,
        models.SRPM._content_type_id.default: _handle_package,
        models.PackageGroup._content_type_id.default: _handle_group_category_comps,
        models.PackageCategory._content_type_id.default: _handle_group_category_comps,
        models.Errata._content_type_id.default: _handle_erratum,
        models.YumMetadataFile._content_type_id.default: _handle_yum_metadata_file,
    }

    if type_id not in handlers:
        return _fail_report('%s is not a supported type for upload' % type_id)

    try:
        handlers[type_id](repo, type_id, unit_key, metadata, file_path, conduit, config)
    except ModelInstantiationError:
        msg = 'metadata for the uploaded file was invalid'
        _LOGGER.exception(msg)
        return _fail_report(msg)
    except StoreFileError:
        msg = 'file could not be deployed into Pulp\'s storage'
        _LOGGER.exception(msg)
        return _fail_report(msg)
    except PackageMetadataError:
        msg = 'metadata for the given package could not be extracted'
        _LOGGER.exception(msg)
        return _fail_report(msg)
    except PulpCodedException, e:
        _LOGGER.exception(e)
        return _fail_report(str(e))
    except:
        msg = 'unexpected error occurred importing uploaded file'
        _LOGGER.exception(msg)
        return _fail_report(msg)

    report = {'success_flag': True, 'summary': '', 'details': {}}
    return report


def _handle_erratum(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    Handles the upload for an erratum. There is no file uploaded so the only
    steps are to save the metadata and optionally link the erratum to RPMs
    in the repository.

    :param repo: The repository to import the package into
    :type  repo: pulp.server.db.model.Repository

    :param type_id: The type_id of the package being uploaded
    :type  type_id: str

    :param unit_key: A dictionary of fields to overwrite introspected field values
    :type  unit_key: dict

    :param metadata: A dictionary of fields to overwrite introspected field values, or None
    :type  metadata: dict or None

    :param file_path: The path to the uploaded package
    :type  file_path: str

    :param conduit: provides access to relevant Pulp functionality
    :type  conduit: pulp.plugins.conduits.upload.UploadConduit

    :param config: plugin configuration for the repository
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    model_class = plugin_api.get_unit_model_by_id(type_id)
    update_fields_inbound(model_class, unit_key or {})
    update_fields_inbound(model_class, metadata or {})

    unit_data = {}
    unit_data.update(metadata or {})
    unit_data.update(unit_key or {})

    unit = model_class(**unit_data)

    unit.save()

    if not config.get_boolean(CONFIG_SKIP_ERRATUM_LINK):
        for model_type in [models.RPM, models.SRPM]:
            pass  # TODO Find out if the unit exists, if it does, associated, if not, create


def _handle_yum_metadata_file(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    Handles the upload for a yum repository metadata file.

    :type  repo: pulp.server.db.model.Repository
    :type  type_id: str
    :type  unit_key: dict
    :type  metadata: dict or None
    :type  file_path: str
    :type  conduit: pulp.plugins.conduits.upload.UploadConduit
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """

    # Validate the user specified data by instantiating the model
    model_data = dict()
    model_data.update(unit_key)
    if metadata:
        model_data.update(metadata)

    # Replicates the logic in yum/sync.py.import_unknown_metadata_files.
    # The local_path variable is removed since it's not included in the metadata when
    # synchronized.
    file_relative_path = model_data.pop('local_path')

    translated_data = models.YumMetadataFile.SERIALIZER().from_representation(model_data)

    model = models.YumMetadataFile(**translated_data)
    model.set_storage_path(os.path.basename(file_relative_path))
    model.save()
    model.import_content(file_relative_path)

    # Move the file to its final storage location in Pulp
    repo_controller.associate_single_unit(conduit.repo, model)


def _handle_group_category_comps(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    Handles the creation of a package group or category.

    If a file was uploaded, treat this as upload of a comps.xml file. If no file was uploaded,
    the process only creates the unit.

    :param repo: The repository to import the package into
    :type  repo: pulp.server.db.model.Repository

    :param type_id: The type_id of the package being uploaded
    :type  type_id: str

    :param unit_key: A dictionary of fields to overwrite introspected field values
    :type  unit_key: dict

    :param metadata: A dictionary of fields to overwrite introspected field values, or None
    :type  metadata: dict or None

    :param file_path: The path to the uploaded package
    :type  file_path: str

    :param conduit: provides access to relevant Pulp functionality
    :type  conduit: pulp.plugins.conduits.upload.UploadConduit

    :param config: plugin configuration for the repository
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    model_class = plugin_api.get_unit_model_by_id(type_id)
    update_fields_inbound(model_class, unit_key or {})
    update_fields_inbound(model_class, metadata or {})

    if file_path is not None and os.path.getsize(file_path) > 0:
        # uploading a comps.xml
        repo_id = repo.repo_id
        _get_and_save_file_units(file_path, group.process_group_element,
                                 group.GROUP_TAG, conduit, repo_id)
        _get_and_save_file_units(file_path, group.process_category_element,
                                 group.CATEGORY_TAG, conduit, repo_id)
        _get_and_save_file_units(file_path, group.process_environment_element,
                                 group.ENVIRONMENT_TAG, conduit, repo_id)
    else:
        # uploading a package group or package category
        unit_data = {}
        unit_data.update(metadata or {})
        unit_data.update(unit_key or {})
        try:
            unit = model_class(**unit_data)
        except TypeError:
            raise ModelInstantiationError()

        unit.save()

        if file_path:
            unit.set_storage_path(os.path.basename(file_path))
            unit.import_content(file_path)

        repo_controller.associate_single_unit(repo, unit)
        repo_controller.rebuild_content_unit_counts(repo)


def _get_and_save_file_units(filename, processing_function, tag, conduit, repo_id):
    """
    Given a comps.xml file, this method decides which groups/categories to get and saves
    the parsed units.

    :param filename:  open file-like object containing metadata
    :type  filename:  file

    :param processing_function:  method to use for generating the units
    :type  processing_function:  function

    :param tag:  XML tag that identifies each unit
    :type  tag:  str

    :param conduit:  provides access to relevant Pulp functionality
    :type  conduit:  pulp.plugins.conduits.upload.UploadConduit

    :param repo_id:  id of the repo into which unit will be uploaded
    :type  repo_id:  str
    """
    process_func = functools.partial(processing_function, repo_id)
    package_info_generator = packages.package_list_generator(filename, tag, process_func)
    for model in package_info_generator:
        model.save()


def _handle_package(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    Handles the upload for an RPM or SRPM.

    This inspects the package contents to determine field values. The unit_key
    and metadata fields overwrite field values determined through package inspection.

    :param repo: The repository to import the package into
    :type  repo: pulp.server.db.model.Repository

    :param type_id: The type_id of the package being uploaded
    :type  type_id: str

    :param unit_key: A dictionary of fields to overwrite introspected field values
    :type  unit_key: dict

    :param metadata: A dictionary of fields to overwrite introspected field values, or None
    :type  metadata: dict or None

    :param file_path: The path to the uploaded package
    :type  file_path: str

    :param conduit: provides access to relevant Pulp functionality
    :type  conduit: pulp.plugins.conduits.upload.UploadConduit

    :param config: plugin configuration for the repository
    :type  config: pulp.plugins.config.PluginCallConfiguration

    :raises PulpCodedException PLP1005: if the checksum type from the user is not recognized
    :raises PulpCodedException PLP1013: if the checksum value from the user does not validate
    """
    try:
        rpm_data = _extract_rpm_data(type_id, file_path)
    except:
        _LOGGER.exception('Error extracting RPM metadata for [%s]' % file_path)
        raise

    model_class = plugin_api.get_unit_model_by_id(type_id)
    update_fields_inbound(model_class, unit_key or {})
    update_fields_inbound(model_class, metadata or {})

    # set checksum and checksumtype
    if metadata:
        checksumtype = metadata.pop('checksumtype', verification.TYPE_SHA256)
        rpm_data['checksumtype'] = verification.sanitize_checksum_type(checksumtype)
        if 'checksum' in metadata:
            rpm_data['checksum'] = metadata.pop('checksum')
            try:
                with open(file_path) as dest_file:
                    verification.verify_checksum(dest_file, rpm_data['checksumtype'],
                                                 rpm_data['checksum'])
            except verification.VerificationException:
                raise PulpCodedException(error_code=platform_errors.PLP1013)
        else:
            rpm_data['checksum'] = _calculate_checksum(rpm_data['checksumtype'], file_path)
    else:
        rpm_data['checksumtype'] = verification.TYPE_SHA256
        rpm_data['checksum'] = _calculate_checksum(rpm_data['checksumtype'], file_path)

    # Update the RPM-extracted data with anything additional the user specified.
    # Allow the user-specified values to override the extracted ones.
    rpm_data.update(metadata or {})
    rpm_data.update(unit_key or {})

    # Validate the user specified data by instantiating the model
    try:
        unit = model_class(**rpm_data)
    except TypeError:
        raise ModelInstantiationError()

    # Extract the repodata snippets
    unit.repodata = rpm_parse.get_package_xml(file_path, sumtype=unit.checksumtype)
    _update_provides_requires(unit)

    # check if the unit has duplicate nevra
    purge.remove_unit_duplicate_nevra(unit, repo)

    unit.set_storage_path(os.path.basename(file_path))
    unit.save()
    unit.import_content(file_path)

    repo_controller.associate_single_unit(repo, unit)
    repo_controller.rebuild_content_unit_counts(repo)


def _update_provides_requires(unit):
    """
    Determines the provides and requires fields based on the RPM's XML snippet and updates
    the model instance.

    :param unit: the unit being added to Pulp; the metadata attribute must already have
                 a key called 'repodata'
    :type  unit: subclass of pulp.server.db.model.ContentUnit
    """
    try:
        # make a guess at the encoding
        codec = 'UTF-8'
        unit.repodata['primary'].encode(codec)
    except UnicodeEncodeError:
        # best second guess we have, and it will never fail due to the nature
        # of the encoding.
        codec = 'ISO-8859-1'
        unit.repodata['primary'].encode(codec)
    fake_xml = FAKE_XML % {'encoding': codec, 'xml': unit.repodata['primary']}
    fake_element = ET.fromstring(fake_xml.encode(codec))
    utils.strip_ns(fake_element)
    primary_element = fake_element.find('package')
    format_element = primary_element.find('format')
    provides_element = format_element.find('provides')
    requires_element = format_element.find('requires')
    unit.provides = map(primary._process_rpm_entry_element,
                        provides_element.findall('entry')) if provides_element else []
    unit.requires = map(primary._process_rpm_entry_element,
                        requires_element.findall('entry')) if requires_element else []


def _extract_rpm_data(type_id, rpm_filename):
    """
    Extract a dict of information for a given RPM or SRPM.

    :param type_id: The type of the unit that is being generated
    :type  type_id: str

    :param rpm_filename: full path to the package to analyze
    :type  rpm_filename: str

    :return: dict of data about the package
    :rtype:  dict
    """
    rpm_data = dict()

    # Read the RPM header attributes for use later
    ts = rpm.TransactionSet()
    ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)
    fd = os.open(rpm_filename, os.O_RDONLY)
    try:
        headers = ts.hdrFromFdno(fd)
        os.close(fd)
    except rpm.error:
        # Raised if the headers cannot be read
        os.close(fd)
        raise

    for k in ['name', 'version', 'release', 'epoch']:
        rpm_data[k] = headers[k]

    if rpm_data['epoch'] is not None:
        rpm_data['epoch'] = str(rpm_data['epoch'])
    else:
        rpm_data['epoch'] = str(0)

    if headers['sourcepackage']:
        if RPMTAG_NOSOURCE in headers.keys():
            rpm_data['arch'] = 'nosrc'
        else:
            rpm_data['arch'] = 'src'
    else:
        rpm_data['arch'] = headers['arch']

    # construct filename from metadata (BZ #1101168)
    if headers[rpm.RPMTAG_SOURCEPACKAGE]:
        if type_id != models.SRPM._content_type_id.default:
            raise PulpCodedValidationException(error_code=error_codes.RPM1002)
        rpm_basefilename = "%s-%s-%s.src.rpm" % (headers['name'],
                                                 headers['version'],
                                                 headers['release'])
    else:
        if type_id != models.RPM._content_type_id.default:
            raise PulpCodedValidationException(error_code=error_codes.RPM1003)
        rpm_basefilename = "%s-%s-%s.%s.rpm" % (headers['name'],
                                                headers['version'],
                                                headers['release'],
                                                headers['arch'])

    rpm_data['relativepath'] = rpm_basefilename
    rpm_data['filename'] = rpm_basefilename

    # This format is, and has always been, incorrect. As of the new yum importer, the
    # plugin will generate these from the XML snippet because the API into RPM headers
    # is atrocious. This is the end game for this functionality anyway, moving all of
    # that metadata derivation into the plugin, so this is just a first step.
    # I'm leaving these in and commented to show how not to do it.
    # rpm_data['requires'] = [(r,) for r in headers['requires']]
    # rpm_data['provides'] = [(p,) for p in headers['provides']]

    rpm_data['buildhost'] = headers['buildhost']
    rpm_data['license'] = headers['license']
    rpm_data['vendor'] = headers['vendor']
    rpm_data['description'] = headers['description']
    rpm_data['build_time'] = headers[rpm.RPMTAG_BUILDTIME]
    # Use the mtime of the file to match what is in the generated xml from
    # rpm_parse.get_package_xml(..)
    file_stat = os.stat(rpm_filename)
    rpm_data['time'] = file_stat[stat.ST_MTIME]

    return rpm_data


def _calculate_checksum(checksum_type, filename):
    m = hashlib.new(checksum_type)
    f = open(filename, 'r')
    while True:
        file_buffer = f.read(CHECKSUM_READ_BUFFER_SIZE)
        if not file_buffer:
            break
        m.update(file_buffer)
    f.close()
    return m.hexdigest()


def _fail_report(message):
    # this is the format returned by the original importer. I'm not sure if
    # anything is actually parsing it
    details = {'errors': [message]}
    return {'success_flag': False, 'summary': '', 'details': details}
