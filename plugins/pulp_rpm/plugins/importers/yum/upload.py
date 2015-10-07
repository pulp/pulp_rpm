import hashlib
import functools
import logging
import os
import shutil
import stat
from xml.etree import cElementTree as ET

import rpm
from pulp.plugins.util import verification
from pulp.plugins.loader import api as plugin_api
from pulp.server.controllers import repository as repo_controller
from pulp.server.exceptions import PulpCodedValidationException, PulpCodedException

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
    :param repo: metadata describing the repository
    :type  repo: pulp.plugins.model.Repository

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

    # Dispatch to process the upload by type
    handlers = {
        models.RPM._content_type_id: _handle_package,
        models.SRPM._content_type_id: _handle_package,
        models.PackageGroup._content_type_id: _handle_group_category,
        models.PackageCategory._content_type_id: _handle_group_category,
        models.Errata._content_type_id: _handle_erratum,
        models.YumMetadataFile._content_type_id: _handle_yum_metadata_file,
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

    :type  repo: pulp.plugins.model.Repository
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


    model_class = plugin_api.get_unit_model_by_id(type_id)
    model = model_class(**model_data)

    # TODO Find out if the unit exists, if it does, associated, if not, create
    unit = conduit.init_unit(model._content_type_id, model.unit_key, model.metadata, None)

    # this save must happen before the link is created, because the link logic
    # requires the unit to have an "id".
    saved_unit = conduit.save_unit(unit)


def _handle_yum_metadata_file(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    Handles the upload for a yum repository metadata file.

    :type  repo: pulp.plugins.model.Repository
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
    model.set_content(file_relative_path)
    model.save()

    # Move the file to its final storage location in Pulp
    repo_controller.associate_single_unit(conduit.repo, model)


def _handle_group_category(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    Handles the creation of a package group or category. If a file was uploaded, treat
    this as upload of a comps file. If no file was uploaded, the process is simply to create
    the unit in Pulp.

    :type  repo: pulp.plugins.model.Repository
    :type  type_id: str
    :type  unit_key: dict
    :type  metadata: dict or None
    :type  file_path: str
    :type  conduit: pulp.plugins.conduits.upload.UploadConduit
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    # If a file was uploaded, assume it is a comps.xml file.
    if file_path is not None and os.path.getsize(file_path) > 0:
        repo_id = repo.id
        _get_file_units(file_path, group.process_group_element,
                        group.GROUP_TAG, conduit, repo_id)
        _get_file_units(file_path, group.process_category_element,
                        group.CATEGORY_TAG, conduit, repo_id)
        _get_file_units(file_path, group.process_environment_element,
                        group.ENVIRONMENT_TAG, conduit, repo_id)
    else:
        # Validate the user specified data by instantiating the model
        try:
            model_class = plugin_api.get_unit_model_by_id(type_id)
            model = model_class(metadata=metadata, **unit_key)
        except TypeError:
            raise ModelInstantiationError()

        unit = conduit.init_unit(model._content_type_id, model.unit_key, model.metadata, None)
        conduit.save_unit(unit)


def _get_file_units(filename, processing_function, tag, conduit, repo_id):
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
        unit = conduit.init_unit(model.TYPE, model.unit_key, model.metadata, None)
        conduit.save_unit(unit)


def _handle_package(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    Handles the upload for an RPM or SRPM. For these types, the unit_key
    and metadata will only contain additions the user wishes to add. The
    typical use case is that the file is uploaded and all of the necessary
    data, both unit key and metadata, are extracted in this method.

    :type  repo: pulp.plugins.model.Repository
    :type  type_id: str
    :type  unit_key: dict
    :type  metadata: dict or None
    :type  file_path: str
    :type  conduit: pulp.plugins.conduits.upload.UploadConduit
    :type  config: pulp.plugins.config.PluginCallConfiguration
    """
    # Extract the RPM key and metadata
    try:
        new_unit_key, new_unit_metadata = _generate_rpm_data(type_id, file_path, metadata)
    except:
        _LOGGER.exception('Error extracting RPM metadata for [%s]' % file_path)
        raise

    # Update the RPM-extracted data with anything additional the user specified.
    # Allow the user-specified values to override the extracted ones.
    new_unit_key.update(unit_key or {})
    new_unit_metadata.update(metadata or {})

    # Validate the user specified data by instantiating the model
    try:
        model_class = plugin_api.get_unit_model_by_id(type_id)
        model = model_class(metadata=new_unit_metadata, **new_unit_key)
    except TypeError:
        raise ModelInstantiationError()

    # Move the file to its final storage location in Pulp
    # TODO this needs to be redone to use set_content() or whatever replaces set_content()
    try:
        unit = conduit.init_unit(model._content_type_id, model.unit_key,
                                 model.metadata, model.relative_path)
        shutil.move(file_path, unit.storage_path) # TODO this should probably be unit._storage_path
    except IOError:
        raise StoreFileError()

    # Extract the repodata snippets
    unit.metadata['repodata'] = rpm_parse.get_package_xml(unit._storage_path, # TODO storage_path?
                                                          sumtype=new_unit_key['checksumtype'])
    _update_provides_requires(unit)
    # check if the unit has duplicate nevra
    purge.remove_unit_duplicate_nevra(model, repo) # TODO ensure the types of this call are correct
    # Save the unit in Pulp
    conduit.save_unit(unit)


def _update_provides_requires(unit):
    """
    Determines the provides and requires fields based on the RPM's XML snippet and updates
    the model instance.

    :param unit: the unit being added to Pulp; the metadata attribute must already have
                 a key called 'repodata'
    :type  unit: pulp.plugins.model.Unit
    """

    try:
        # make a guess at the encoding
        codec = 'UTF-8'
        unit.metadata['repodata']['primary'].encode(codec)
    except UnicodeEncodeError:
        # best second guess we have, and it will never fail due to the nature
        # of the encoding.
        codec = 'ISO-8859-1'
        unit.metadata['repodata']['primary'].encode(codec)
    fake_xml = FAKE_XML % {'encoding': codec, 'xml': unit.metadata['repodata']['primary']}
    fake_element = ET.fromstring(fake_xml.encode(codec))
    utils.strip_ns(fake_element)
    primary_element = fake_element.find('package')
    format_element = primary_element.find('format')
    provides_element = format_element.find('provides')
    requires_element = format_element.find('requires')
    unit.metadata['provides'] = map(primary._process_rpm_entry_element,
                                    provides_element.findall('entry')) if provides_element else []
    unit.metadata['requires'] = map(primary._process_rpm_entry_element,
                                    requires_element.findall('entry')) if requires_element else []


def _generate_rpm_data(type_id, rpm_filename, user_metadata=None):
    """
    For the given RPM, analyzes its metadata to generate the appropriate unit
    key and metadata fields, returning both to the caller.

    :param type_id: The type of the unit that is being generated
    :type  type_id: str
    :param rpm_filename: full path to the RPM to analyze
    :type  rpm_filename: str
    :param user_metadata: user supplied metadata about the unit. This is optional.
    :type  user_metadata: dict

    :return: tuple of unit key and unit metadata for the RPM
    :rtype:  tuple
    """

    # Expected metadata fields:
    # "vendor", "description", "buildhost", "license", "vendor", "requires", "provides",
    # "relativepath", "filename"
    #
    # Expected unit key fields:
    # "name", "epoch", "version", "release", "arch", "checksumtype", "checksum"

    unit_key = dict()
    metadata = dict()

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

    # -- Unit Key -----------------------
    # Checksum
    if user_metadata and user_metadata.get('checksum_type'):
        user_checksum_type = user_metadata.get('checksum_type')
        user_checksum_type = verification.sanitize_checksum_type(user_checksum_type)
        unit_key['checksumtype'] = user_checksum_type
    else:
        unit_key['checksumtype'] = verification.TYPE_SHA256
    unit_key['checksum'] = _calculate_checksum(unit_key['checksumtype'], rpm_filename)

    # Name, Version, Release, Epoch
    for k in ['name', 'version', 'release', 'epoch']:
        unit_key[k] = headers[k]

    # Epoch munging
    if unit_key['epoch'] is None:
        unit_key['epoch'] = str(0)
    else:
        unit_key['epoch'] = str(unit_key['epoch'])

    # Arch
    if headers['sourcepackage']:
        if RPMTAG_NOSOURCE in headers.keys():
            unit_key['arch'] = 'nosrc'
        else:
            unit_key['arch'] = 'src'
    else:
        unit_key['arch'] = headers['arch']

    # -- Unit Metadata ------------------

    # construct filename from metadata (BZ #1101168)
    if headers[rpm.RPMTAG_SOURCEPACKAGE]:
        if type_id != models.SRPM._content_type_id:
            raise PulpCodedValidationException(error_code=error_codes.RPM1002)
        rpm_basefilename = "%s-%s-%s.src.rpm" % (headers['name'],
                                                 headers['version'],
                                                 headers['release'])
    else:
        if type_id != models.RPM._content_type_id:
            raise PulpCodedValidationException(error_code=error_codes.RPM1003)
        rpm_basefilename = "%s-%s-%s.%s.rpm" % (headers['name'],
                                                headers['version'],
                                                headers['release'],
                                                headers['arch'])

    metadata['relativepath'] = rpm_basefilename
    metadata['filename'] = rpm_basefilename

    # This format is, and has always been, incorrect. As of the new yum importer, the
    # plugin will generate these from the XML snippet because the API into RPM headers
    # is atrocious. This is the end game for this functionality anyway, moving all of
    # that metadata derivation into the plugin, so this is just a first step.
    # I'm leaving these in and commented to show how not to do it.
    # metadata['requires'] = [(r,) for r in headers['requires']]
    # metadata['provides'] = [(p,) for p in headers['provides']]

    metadata['buildhost'] = headers['buildhost']
    metadata['license'] = headers['license']
    metadata['vendor'] = headers['vendor']
    metadata['description'] = headers['description']
    metadata['build_time'] = headers[rpm.RPMTAG_BUILDTIME]
    # Use the mtime of the file to match what is in the generated xml from
    # rpm_parse.get_package_xml(..)
    file_stat = os.stat(rpm_filename)
    metadata['time'] = file_stat[stat.ST_MTIME]

    return unit_key, metadata


def _calculate_checksum(checksum_type, filename):
    m = hashlib.new(checksum_type)
    f = open(filename, 'r')
    while 1:
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
