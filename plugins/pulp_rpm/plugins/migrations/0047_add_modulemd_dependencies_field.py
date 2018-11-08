from pulp.server.db.connection import get_collection
from pulp.server.db.migrations.lib import utils


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


def _get_dependencies(module):
    """
    Parse dependencies of given modulemd document

    :param module: Modulemd metadata document object.
    :type module: gi.repository.Modulemd.Module
    :return: list of dictionaries, where for each dictionary, key is a module name and value
             is a list of streams
    :rtype: list
    """
    loadlibmodulemd()
    res = []
    deps = module.get_dependencies()
    for dep in deps:
        d = {}
        for k, v in dep.get_requires().iteritems():
            d[k] = v.get()
            res.append(d)
    return res


def migrate_modulemd(collection, unit):
    """
    Parse dependencies for single module unit and populate the field accordingly.

    :param collection: a collection of Modulemd units
    :type collection: pymongo.collection.Collection
    :param unit: the Modulemd unit being migrated
    :type unit: dict
    """
    loadlibmodulemd()
    path = unit.get('_storage_path')
    module = Modulemdlib.objects_from_file(path)
    dependencies = _get_dependencies(module[0])
    delta = {'dependencies': dependencies}
    collection.update_one({'_id': unit['_id']}, {'$set': delta})


def migrate(*args, **kwargs):
    """
    Populate the Modulemd unit dependencies field.

    :param args: unused
    :type args: list
    :param kwargs: unused
    type kwargs: dict
    """
    modulemd_collection = get_collection('units_modulemd')
    modulemd_selection = modulemd_collection.find(
        {'dependencies': {'$exists': False}}, ['_storage_path']).batch_size(100)
    total_modulemd_units = modulemd_selection.count()
    with utils.MigrationProgressLog('Modulemd', total_modulemd_units) as progress_log:
        for modulemd in modulemd_selection:
            migrate_modulemd(modulemd_collection, modulemd)
            progress_log.progress()
