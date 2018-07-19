import os

from hashlib import sha256
from uuid import uuid4

from mongoengine import Q, NotUniqueError

from pulp.server.controllers import repository as repository_controller
from pulp.server.managers.repo._common import get_working_directory

from pulp_rpm.plugins.db.models import Modulemd, ModulemdDefaults, RPM
from pulp_rpm.plugins.importers.yum.repomd import modules
from pulp_rpm.plugins.importers.yum.parse import rpm


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


def add_modulemd(repository, modulemd, model):
    """
    Add the specified modulemd.

    Created as needed then added to the repository.

    :param repository: A repository.
    :type repository: pulp.server.db.model.Repository
    :param modulemd: A modulemd (libmodulemd) document object.
    :type modulemd: gi.repository.Modulemd.Module
    :param model: The Modulemd model object to add.
    :type model: pulp_rpm.plugins.db.models.Modulemd
    """
    path = os.path.join(
        get_working_directory(),
        str(uuid4()))
    document = modulemd.dumps()
    with open(path, 'w+') as fp:
        fp.write(document)
    model.checksum = sha256(document).hexdigest()
    try:
        model.save_and_import_content(path)
    except NotUniqueError:
        model = Modulemd.objects.get(**model.unit_key)
    repository_controller.associate_single_unit(repository, model)


def add_modulemds(repository, modulemds):
    """
    Add the collection of modulemd content to the repository.

    The content is created as needed and added to the repository.

    :param repository: A repository.
    :type repository: pulp.server.db.model.Repository
    :param modulemds: A list of gi.repository.Modulemd.Module.
    :type modulemds: collections.Iterable
    :return: The set of content unit keys contained in the repository
             that are not contained in the collection of modulemds to be added.
    :rtype: set
    """
    wanted = set()
    inventory = get_inventory(repository, Model=Modulemd)
    for modulemd in modulemds:
        model = modules.process_modulemd_document(modulemd)
        key = model.NAMED_TUPLE(**model.unit_key)
        wanted.add(key)
        if key in inventory:
            continue
        add_modulemd(repository, modulemd, model)
    remainder = set(inventory.iterkeys()).difference(wanted)
    return remainder


def remove_modulemds(repository, modulemds):
    """
    Remove Modulemd content from the repository.

    The content is removed from the repository along with RPMs
    listed as artifacts. The artifacts are not removed if referenced
    by any other modulemd.

    :param repository: A repository.
    :type repository: pulp.server.db.model.Repository
    :param modulemds: A set of Modulemd unit keys to be removed.
    :type modulemds: set
    """
    if not modulemds:
        return

    uq = Q()
    for key in modulemds:
        uq |= Q(**key._asdict())

    q_set = repository_controller.find_repo_content_units(
        repository,
        repo_content_unit_q=Q(unit_type_id=Modulemd.TYPE_ID),
        yield_content_unit=True,
        units_q=uq)

    def content():
        for modulemd in q_set:
            for artifact in modulemd.artifacts:
                nevra = rpm.nevra(artifact)
                pq = Q(
                    name=nevra[0],
                    epoch=unicode(nevra[1]),
                    version=nevra[2],
                    release=nevra[3],
                    arch=nevra[4])
                pq_set = repository_controller.find_repo_content_units(
                    repository,
                    units_q=pq,
                    repo_content_unit_q=Q(unit_type_id=RPM.TYPE_ID),
                    unit_fields=[],
                    yield_content_unit=True)
                for package in pq_set:
                    rq_set = repository_controller.find_repo_content_units(
                        repository,
                        limit=1,
                        units_q=Q(artifacts=artifact),
                        repo_content_unit_q=Q(
                            unit_type_id=modulemd.type_id,
                            unit_id={'$ne': modulemd.id}))
                    if not tuple(rq_set):
                        yield package
            yield modulemd

    repository_controller.disassociate_units(repository, content())


def add_default(repository, default, model):
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
    """
    path = os.path.join(
        get_working_directory(),
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


def add_defaults(repository, defaults):
    """
    Add the collection of modulemd-defaults content to the repository.

    The content is created as needed and added to the repository.
    Matching content already contained in the repository is compared
    by checksum and updated as needed.

    :param repository: A repository.
    :type repository: pulp.server.db.model.Repository
    :param defaults: A list of gi.repository.Modulemd.Module.
    :type defaults: collections.Iterable
    :return: The set of content unit keys contained in the repository
             that are not contained in the collection of defaults to be added.
    :rtype: set
    """
    wanted = set()
    inventory = get_inventory(repository, Model=ModulemdDefaults)
    for default in defaults:
        model = modules.process_defaults_document(default)
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
        add_default(repository, default, model)
    remainder = set(inventory.iterkeys()).difference(wanted)
    return remainder


def remove_defaults(repository, defaults):
    """
    Remove ModulemdDefaults content from the repository.

    :param repository: A repository.
    :type repository: pulp.server.db.model.Repository
    :param defaults: A set of ModulemdDefaults unit keys to be removed.
    :type defaults: set
    """
    if not defaults:
        return

    uq = Q()
    for key in defaults:
        uq |= Q(**key._asdict())

    q_set = repository_controller.find_repo_content_units(
        repository,
        repo_content_unit_q=Q(unit_type_id=ModulemdDefaults.TYPE_ID),
        yield_content_unit=True,
        units_q=uq)

    repository_controller.disassociate_units(repository, q_set)


def load(metadata, working_dir):
    """
    Load the "modules" metadata.

    :param metadata: The metadata downloaded from the remote repository.
    :type metadata: pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param working_dir: Absolute path to a directory used for temporary files.
    :type working_dir: str
    :return: Two lists of: Modulemd.Module and Modulemd.Defaults
    :rtype: tuple
    """
    fp = metadata.get_metadata_file_handle(modules.METADATA_FILE_NAME)
    if not fp:
        return (), ()
    path = os.path.join(
        working_dir,
        str(uuid4()))
    with open(path, 'w+') as fp_w:
        while True:
            bfr = fp.read(1024000)
            if bfr:
                fp_w.write(bfr)
            else:
                break
    loaded = modules.from_file(path)
    os.unlink(path)
    return loaded


def synchronize(repository, metadata, mirror=False):
    """
    Synchronize the modularity related content.

    :param repository: A repository.
    :type repository: pulp.server.db.model.Repository
    :param metadata: The metadata downloaded from the remote repository.
    :type metadata: pulp_rpm.plugins.importers.yum.repomd.metadata.MetadataFiles
    :param mirror: Mirror mode. When enabled: content contained in the repository
         that is not also contained in the metadata is removed.
    :type mirror: bool
    """
    modulemds, defaults = load(metadata, get_working_directory())
    remainder = add_modulemds(repository, modulemds)
    if mirror:
        remove_modulemds(repository, remainder)
    remainder = add_defaults(repository, defaults)
    if mirror:
        remove_defaults(repository, remainder)
