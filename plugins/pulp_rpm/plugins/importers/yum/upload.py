import functools
from gettext import gettext as _
import logging
import os
import stat
from mongoengine import NotUniqueError

from pulp.plugins.loader import api as plugin_api
from pulp.server.controllers import repository as repo_controller
from pulp.server.exceptions import PulpCodedValidationException, PulpCodedException
from pulp.server.exceptions import error_codes as platform_errors
from pulp.server import util
import rpm

from pulp_rpm.plugins import error_codes
from pulp_rpm.plugins.controllers import errata as errata_controller
from pulp_rpm.plugins.db import models
from pulp_rpm.plugins.importers.yum import purge, utils
from pulp_rpm.plugins.importers.yum.parse import rpm as rpm_parse
from pulp_rpm.plugins.importers.yum.repomd import primary, group, packages, filelists

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


class RPMOnlyDRPMsAreNotSupported(Exception):
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
        models.DRPM._content_type_id.default: _handle_package,
        models.PackageGroup._content_type_id.default: _handle_group_category_comps,
        models.PackageCategory._content_type_id.default: _handle_group_category_comps,
        models.PackageEnvironment._content_type_id.default: _handle_group_category_comps,
        models.PackageLangpacks._content_type_id.default: _handle_group_category_comps,
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
    except RPMOnlyDRPMsAreNotSupported:
        msg = 'RPM only DRPMs are not supported'
        _LOGGER.warning(msg)
        return _fail_report(msg)
    except PulpCodedException, e:
        _LOGGER.exception(e)
        return _fail_report(str(e))
    except Exception as e:
        msg = 'unexpected error occurred importing uploaded file: %s' % e
        _LOGGER.exception(msg)
        return _fail_report(msg)

    report = {'success_flag': True, 'summary': '', 'details': {}}
    return report


def _handle_erratum(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    Handles the upload for an erratum. There is no file uploaded so the only
    steps are to save the metadata and optionally link the erratum to RPMs
    in the repository.

    NOTE: For now errata is handled differently than other units. Uploaded erratum should not
    overwrite the existing one if the latter exists, they should be merged. This is only because
    of the way erratum is stored in the MongoDB and it is in `our plans`_ to re-think how to do
    it correctly.

    .. _our plans: https://pulp.plan.io/issues/1803

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
    errata_controller.create_or_update_pkglist(unit, repo.repo_id)

    try:
        unit.save()
    except NotUniqueError:
        existing_unit = model_class.objects.filter(**unit_key).first()
        existing_unit.merge_errata(unit)
        unit = existing_unit
        unit.save()

    if not config.get_boolean(CONFIG_SKIP_ERRATUM_LINK):
        repo_controller.associate_single_unit(repo, unit)


def _handle_yum_metadata_file(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    Handles the upload for a Yum repository metadata file.

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

    model = models.YumMetadataFile(**unit_data)
    model.set_storage_path(os.path.basename(file_path))
    try:
        model.save_and_import_content(file_path)
    except NotUniqueError:
        model = model.__class__.objects.get(**model.unit_key)

    repo_controller.associate_single_unit(conduit.repo, model)


def _handle_group_category_comps(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    Handles the creation of a package group, category or environment.

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
        _get_and_save_file_units(file_path, group.process_group_element,
                                 group.GROUP_TAG, conduit, repo)
        _get_and_save_file_units(file_path, group.process_category_element,
                                 group.CATEGORY_TAG, conduit, repo)
        _get_and_save_file_units(file_path, group.process_environment_element,
                                 group.ENVIRONMENT_TAG, conduit, repo)
        _get_and_save_file_units(file_path, group.process_langpacks_element,
                                 group.LANGPACKS_TAG, conduit, repo)
    else:
        # uploading a package group, package category or package environment
        unit_data = {}
        unit_data.update(metadata or {})
        unit_data.update(unit_key or {})
        try:
            unit = model_class(**unit_data)
        except TypeError:
            raise ModelInstantiationError()

        try:
            unit.save()
        except NotUniqueError:
            unit = unit.__class__.objects.filter(**unit.unit_key).first()
            for k, v in unit_data.items():
                setattr(unit, k, v)
            unit.save()

        repo_controller.associate_single_unit(repo, unit)


def _get_and_save_file_units(filename, processing_function, tag, conduit, repo):
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

    :param repo: The repository to import the package into
    :type  repo: pulp.server.db.model.Repository
    """
    repo_id = repo.repo_id
    process_func = functools.partial(processing_function, repo_id)
    package_info_generator = packages.package_list_generator(filename, tag, process_func)
    for model in package_info_generator:
        try:
            model.save()
        except NotUniqueError:
            model = model.__class__.objects.filter(**model.unit_key).first()

        repo_controller.associate_single_unit(repo, model)


def _handle_package(repo, type_id, unit_key, metadata, file_path, conduit, config):
    """
    Handles the upload for an RPM, SRPM or DRPM.

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
        if type_id == models.DRPM._content_type_id.default:
            rpm_data = _extract_drpm_data(file_path)
        else:
            rpm_data = _extract_rpm_data(type_id, file_path)
    except:
        _LOGGER.exception('Error extracting RPM metadata for [%s]' % file_path)
        raise

    # metadata can be None
    metadata = metadata or {}

    model_class = plugin_api.get_unit_model_by_id(type_id)
    update_fields_inbound(model_class, unit_key or {})
    update_fields_inbound(model_class, metadata or {})

    with open(file_path) as fp:
        sums = util.calculate_checksums(fp, models.RpmBase.DEFAULT_CHECKSUM_TYPES)

    # validate checksum if possible
    if metadata.get('checksum'):
        checksumtype = metadata.pop('checksum_type', util.TYPE_SHA256)
        checksumtype = util.sanitize_checksum_type(checksumtype)
        if checksumtype not in sums:
            raise PulpCodedException(error_code=error_codes.RPM1009, checksumtype=checksumtype)
        if metadata['checksum'] != sums[checksumtype]:
            raise PulpCodedException(error_code=platform_errors.PLP1013)
        _LOGGER.debug(_('Upload checksum matches.'))

    # Save all uploaded RPMs with sha256 in the unit key, since we can now publish with other
    # types, regardless of what is in the unit key.
    rpm_data['checksumtype'] = util.TYPE_SHA256
    rpm_data['checksum'] = sums[util.TYPE_SHA256]
    # keep all available checksum values on the model
    rpm_data['checksums'] = sums

    # Update the RPM-extracted data with anything additional the user specified.
    # Allow the user-specified values to override the extracted ones.
    rpm_data.update(metadata or {})
    rpm_data.update(unit_key or {})

    # Validate the user specified data by instantiating the model
    try:
        unit = model_class(**rpm_data)
    except TypeError:
        raise ModelInstantiationError()

    if type_id != models.DRPM._content_type_id.default:
        # Extract/adjust the repodata snippets
        repodata = rpm_parse.get_package_xml(file_path, sumtype=unit.checksumtype)
        _update_provides_requires(unit, repodata)
        _update_files(unit, repodata)
        unit.modify_xml(repodata)

    # check if the unit has duplicate nevra
    purge.remove_unit_duplicate_nevra(unit, repo)

    unit.set_storage_path(os.path.basename(file_path))
    try:
        unit.save_and_import_content(file_path)
    except NotUniqueError:
        unit = unit.__class__.objects.filter(**unit.unit_key).first()

    if rpm_parse.signature_enabled(config):
        rpm_parse.filter_signature(unit, config)
    repo_controller.associate_single_unit(repo, unit)


def _update_provides_requires(unit, repodata):
    """
    Determines the provides and requires fields based on the RPM's XML snippet and updates
    the model instance.

    :param unit: the unit being added to Pulp; the metadata attribute must already have
                 a key called 'repodata'
    :type  unit: subclass of pulp.server.db.model.ContentUnit
    :param repodata: xml snippets to analyze
    :type  repodata: dict
    """
    fake_element = utils.fake_xml_element(repodata['primary'])
    utils.strip_ns(fake_element)
    primary_element = fake_element.find('package')
    format_element = primary_element.find('format')
    provides_element = format_element.find('provides')
    requires_element = format_element.find('requires')
    unit.provides = map(primary._process_rpm_entry_element,
                        provides_element.findall('entry')) if provides_element else []
    unit.requires = map(primary._process_rpm_entry_element,
                        requires_element.findall('entry')) if requires_element else []


def _update_files(unit, repodata):
    """
    Determines the files based on the RPM's XML snippet and updates the model
    instance.

    :param unit: the unit being added to Pulp; the metadata attribute must already have
                 a key called 'repodata'
    :type  unit: subclass of pulp.server.db.model.ContentUnit
    :param repodata: xml snippets to analyze
    :type  repodata: dict
    """
    fake_element = utils.fake_xml_element(repodata['filelists'])
    package_element = fake_element.find('package')
    _, unit.files = filelists.process_package_element(package_element)


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
    headers = rpm_parse.package_headers(rpm_filename)

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
    rpm_data['signing_key'] = rpm_parse.package_signature(headers)

    return _encode_as_utf8(rpm_data)


def _extract_drpm_data(drpm_filename):
    """
    Extract a dict of information for a given DRPM.

    :param drpm_filename: full path to the package to analyze
    :type  drpm_filename: str

    :return: dict of data about the package
    :rtype:  dict
    """
    drpm_data = dict()

    headers = rpm_parse.drpm_package_info(drpm_filename)

    try:  # "handle" rpm-only drpms (without rpm header)
        rpm_headers = rpm_parse.package_headers(drpm_filename)
    except rpm.error:
        raise RPMOnlyDRPMsAreNotSupported(drpm_filename)

    drpm_data['signing_key'] = rpm_parse.package_signature(rpm_headers)
    drpm_data['arch'] = rpm_headers['arch']

    old_nevr = old_name, old_epoch, old_version, old_release = rpm_parse.nevr(headers["old_nevr"])
    new_nevr = new_name, new_epoch, new_version, new_release = rpm_parse.nevr(headers["nevr"])

    drpm_data['sequence'] = headers["old_nevr"] + "-" + headers["seq"]

    drpm_data['epoch'] = str(new_epoch)
    drpm_data['oldepoch'] = str(old_epoch)

    drpm_data['version'] = str(new_version)
    drpm_data['oldversion'] = str(old_version)

    drpm_data['release'] = new_release
    drpm_data['oldrelease'] = old_release

    drpm_data['new_package'] = new_name
    drpm_data['size'] = os.stat(drpm_filename)[stat.ST_SIZE]

    old_evr = rpm_parse.nevr_to_evr(*old_nevr)
    new_evr = rpm_parse.nevr_to_evr(*new_nevr)
    drpm_data['filename'] = "drpms/%s-%s_%s.%s.drpm" % (new_name, rpm_parse.evr_to_str(*old_evr),
                                                        rpm_parse.evr_to_str(*new_evr),
                                                        drpm_data['arch'])

    return _encode_as_utf8(drpm_data)


def _fail_report(message):
    # this is the format returned by the original importer. I'm not sure if
    # anything is actually parsing it
    details = {'errors': [message]}
    return {'success_flag': False, 'summary': '', 'details': details}


def _encode_as_utf8(data_dict):
    """
    Ensure all string values in `data_dict` are encoded as utf-8.

    The dict is changed in place. Any strings that are not utf-8
    encoded, will get replacements chars, so that the locations that
    failed to be encoded will still be visible.

    :param data_dict: A ordinary dictionary.
    :type  data_dict: dict

    :return: dict with all string values utf-8 encoded.
    :rtype:  dict
    """
    for key, val in data_dict.items():
        if isinstance(val, str):
            data_dict[key] = val.decode('utf-8', 'replace').encode('utf-8')
    return data_dict
