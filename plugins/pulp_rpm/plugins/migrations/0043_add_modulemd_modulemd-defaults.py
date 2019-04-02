from gettext import gettext as _
import gzip
import logging
import os
from uuid import uuid4
from hashlib import sha256

import bson
from mongoengine import Q, NotUniqueError

from pulp.plugins.loader import api as plugin_api
from pulp.server.controllers import repository as repository_controller
from pulp.server.db.model import Repository
from pulp.server.db import connection
from pulp_rpm.plugins.db.models import YumMetadataFile
from pulp_rpm.plugins.db.models import Modulemd, ModulemdDefaults


_logger = logging.getLogger('pulp_rpm.plugins.migrations.0043')

METADATA_FILE_NAME = 'modules'

Modulemdlib = None


def loadlibmodulemd():
    """
    Load the gobject module and import the Modulemd (libmodulemd) lib.

    The gobject module and underlying C lib is not fork-safe and
    must be loaded after the WSGI process has forked.
    """
    import gi
    global Modulemdlib
    lib = 'Modulemd'
    gi.require_version(lib, '1.0')
    Modulemdlib = getattr(__import__('gi.repository', fromlist=[lib]), lib)


def process_modulemd_document(module):
    """
    Process a parsed modules.yaml modulemd document into a model instance.

    :param module: Modulemd metadata document object.
    :type module: gi.repository.Modulemd.Module
    :return: Modulemd model object.
    :rtype: pulp_rpm.plugins.db.models.Modulemd
    """
    loadlibmodulemd()
    modulemd_document = {
        'name': module.peek_name(),
        'stream': module.peek_stream(),
        'version': module.peek_version(),
        'context': module.peek_context(),
        'arch': module.peek_arch() or 'noarch',
        'summary': module.peek_summary(),
        'description': module.peek_description(),
        'profiles': _get_profiles(module),
        'artifacts': module.peek_rpm_artifacts().get(),
    }

    return Modulemd(**modulemd_document)


def process_defaults_document(module):
    """
    Process a parsed modules.yaml modulemd-defaults document into a model instance.

    repo_id should be added during sync or upload before saving the unit.

    :param module: Modulemd-defaults metadata document object.
    :type module: gi.repository.Modulemd.Defaults
    :return: ModulemdDefaults model object.
    :rtype: pulp_rpm.plugins.db.models.ModulemdDefaults
    """
    loadlibmodulemd()
    modulemd_defaults_document = {
        'name': module.peek_module_name(),
        'repo_id': None,
        'stream': module.peek_default_stream(),
        'profiles': _get_profile_defaults(module),
    }

    return ModulemdDefaults(**modulemd_defaults_document)


def _get_profiles(module):
    """
    Parse profiles of given modulemd document

    :param module: Modulemd metadata document object.
    :type module: gi.repository.Modulemd.Module
    :return: key:value, where key is a profile name and value is set of packages.
    :rtype: dict
    """
    loadlibmodulemd()
    d = module.peek_profiles()
    for k, v in d.items():
        d[k] = v.peek_rpms().get()
    return d


def _get_profile_defaults(module):
    """
    Parse stream profile defaults of a given modulemd-defaults document.

    Dictionary has to be encoded due to MongoDB limitations for keys. MongoDB doesn't allow dots
    in the keys but it's a very common case for stream names.

    :param module: Modulemd-defaults metadata document object.
    :type module: gi.repository.Modulemd.Defaults
    :return: BSON encoded key:value, where key is a stream and value is a list of default profiles.
    :rtype: bson.BSON
    """
    loadlibmodulemd()
    profile_defaults = {}
    for stream, defaults in module.peek_profile_defaults().items():
        profile_defaults[stream] = defaults.get()
    return bson.BSON.encode(profile_defaults)


def from_file(path):
    """
    Parse profiles of given modulemd document

    :param path: An optional path to the modules.yaml file
    :type path: str
    :return: 2 lists of Modulemdlib.Module and Modulemdlib.Defaults
    :rtype: tuple
    """
    loadlibmodulemd()
    modulemd = []
    defaults = []
    modules = Modulemdlib.objects_from_file(path)
    for module in modules:
        if isinstance(module, Modulemdlib.Module):
            modulemd.append(module)
        elif isinstance(module, Modulemdlib.Defaults):
            defaults.append(module)
    return modulemd, defaults


def add_modulemd(repository, modulemd, model, working_dir):
    """
    Add the specified modulemd.

    Created as needed then added to the repository.

    :param repository: A repository.
    :type repository: pulp.server.db.model.Repository
    :param modulemd: A modulemd (libmodulemd) document object.
    :type modulemd: gi.repository.Modulemd.Module
    :param model: The Modulemd model object to add.
    :type model: pulp_rpm.plugins.db.models.Modulemd
    :param working_dir: The absolute path to a temporary directory to write out the file
    :type working_dir: str
    """
    path = os.path.join(working_dir, str(uuid4()))
    document = modulemd.dumps()
    with open(path, 'w+') as fp:
        fp.write(document)
    model.checksum = sha256(document).hexdigest()
    try:
        model.save_and_import_content(path)
    except NotUniqueError:
        model = Modulemd.objects.get(**model.unit_key)
    repository_controller.associate_single_unit(repository, model)


def get_inventory(repository, Model):
    """
    Get content that is already contained in the repository.

    :param repository: A repository.
    :type repository: pulp.server.db.model.Repository
    :param Model: The content model class.
    :type Model: pulp.server.db.model.FileContent
    :return: A dict keyed by the unit key tuple and a value of checksum.
    """
    inventory = {}
    fields = ('id', 'checksum')
    fields += Model.unit_key_fields
    q_set = repository_controller.find_repo_content_units(
        repository,
        repo_content_unit_q=Q(unit_type_id=Model.TYPE_ID),
        unit_fields=fields,
        yield_content_unit=True)
    for m in q_set:
        key = m.NAMED_TUPLE(**m.unit_key)
        inventory[key] = m.checksum
    return inventory


def add_modulemds(repository, modulemds, working_dir):
    """
    Add the collection of modulemd content to the repository.

    The content is created as needed and added to the repository.

    :param repository: A repository.
    :type repository: pulp.server.db.model.Repository
    :param modulemds: A list of gi.repository.Modulemd.Module.
    :type modulemds: collections.Iterable
    :param working_dir: The absolute path to a temporary directory to write out the file
    :type working_dir: str
    :return: The set of content unit keys contained in the repository
             that are not contained in the collection of modulemds to be added.
    :rtype: set
    """
    wanted = set()
    inventory = get_inventory(repository, Model=Modulemd)
    for modulemd in modulemds:
        model = process_modulemd_document(modulemd)
        key = model.NAMED_TUPLE(**model.unit_key)
        wanted.add(key)
        if key in inventory:
            continue
        add_modulemd(repository, modulemd, model, working_dir)
    remainder = set(inventory.iterkeys()).difference(wanted)
    return remainder


def add_default(repository, default, model, working_dir):
    """
    Add the specified modulemd-defaults.

    Created as needed then added to the repository.
    Existing content is updated.

    :param repository: A repository.
    :type repository: pulp.server.db.model.Repository
    :param default: A modulemd-default (libmodulemd) document object.
    :type default: gi.repository.Modulemd.Defaults
    :param model: The ModulemdDefaults model object to add.
    :type model: pulp_rpm.plugins.db.models.ModulemdDefaults
    :param working_dir: The absolute path to a temporary directory to write out the file
    :type working_dir: str
    """
    path = os.path.join(
        working_dir,
        str(uuid4()))
    document = default.dumps()
    with open(path, 'w+') as fp:
        fp.write(document)
    model.checksum = sha256(document).hexdigest()
    model.repo_id = repository.repo_id
    try:
        model.save_and_import_content(path)
    except NotUniqueError:
        updated = ModulemdDefaults.objects.get(**model.unit_key)
        updated.update(
            stream=model.stream,
            profiles=model.profiles,
            checksum=model.checksum)
        updated.safe_import_content(path)
        model = updated
    repository_controller.associate_single_unit(repository, model)


def add_defaults(repository, defaults, working_dir):
    """
    Add the collection of modulemd-defaults content to the repository.

    The content is created as needed and added to the repository.
    Matching content already contained in the repository is compared
    by checksum and updated as needed.

    :param repository: A repository.
    :type repository: pulp.server.db.model.Repository
    :param defaults: A list of gi.repository.Modulemd.Module.
    :type defaults: collections.Iterable
    :param working_dir: The absolute path to a temporary directory to write out the file
    :type working_dir: str
    :return: The set of content unit keys contained in the repository
             that are not contained in the collection of defaults to be added.
    :rtype: set
    """
    wanted = set()
    inventory = get_inventory(repository, Model=ModulemdDefaults)
    for default in defaults:
        model = process_defaults_document(default)
        model.repo_id = repository.repo_id
        key = model.NAMED_TUPLE(**model.unit_key)
        wanted.add(key)
        try:
            checksum = inventory[key]
        except KeyError:
            pass
        else:
            document = default.dumps()
            model.checksum = sha256(document).hexdigest()
            if checksum == model.checksum:
                continue
        add_default(repository, default, model, working_dir)
    remainder = set(inventory.iterkeys()).difference(wanted)
    return remainder


def load(metadata, working_dir):
    """
    Load the "modules" metadata.

    :param metadata: The file object with modulemd.
    :type metadata: file
    :param working_dir: Absolute path to a directory used for temporary files.
    :type working_dir: str
    :return: Two lists of: Modulemdlib.Module and Modulemdlib.Defaults
    :rtype: tuple
    """
    if not metadata:
        return (), ()
    path = os.path.join(
        working_dir,
        str(uuid4()))
    with open(path, 'w+') as fp_w:
        while True:
            bfr = metadata.read(1024000)
            if bfr:
                fp_w.write(bfr)
            else:
                break
    loaded = from_file(path)
    os.unlink(path)
    return loaded


def migrate(*args, **kwargs):

    plugin_api.initialize()
    db = connection.get_database()
    repo_content = db['repo_content_units']
    unit_ids = [unit['unit_id'] for unit in repo_content.find({"unit_type_id":
                                                               "yum_repo_metadata_file"})]
    metadatafiles = YumMetadataFile.objects(__raw__={'data_type': 'modules',
                                                     '_id': {'$in': unit_ids}})
    repos_to_republish = set()
    for file in metadatafiles:
        repository = Repository.objects.get(repo_id=file.repo_id)
        try:
            with gzip.open(file._storage_path, 'r') as fp:
                working_dir = "/var/cache/pulp"
                modulemds, defaults = load(fp, working_dir)
                add_modulemds(repository, modulemds, working_dir)
                add_defaults(repository, defaults, working_dir)
                repository_controller.disassociate_units(repository, [file])
                repository_controller.rebuild_content_unit_counts(repository)
                repos_to_republish.add(file.repo_id)
        except IOError:
            with open(file._storage_path, 'r') as fp:
                working_dir = "/var/cache/pulp"
                modulemds, defaults = load(fp, working_dir)
                add_modulemds(repository, modulemds, working_dir)
                add_defaults(repository, defaults, working_dir)
                repository_controller.disassociate_units(repository, [file])
                repository_controller.rebuild_content_unit_counts(repository)
                repos_to_republish.add(file.repo_id)
    if repos_to_republish:
        with open('/var/lib/pulp/0043_add_modulemd_modulemd-defaults.txt', 'w') as f:
            f.write(str(list(repos_to_republish)))
            msg = _('***Note. You should re-publish the list of repos found in\n'
                    '   %s. This migration added\n'
                    '   Modulemd and Modulemd-Defaults as content types. The YumMetadataFiles\n'
                    '   that were previously used to represent Modulemd content will be removed\n'
                    '   next time orphan clean up task runs. Re-publish the repositories to avoid\n'
                    '   any problems for clients looking for Modulemd content.' % f.name)
            _logger.info(msg)
