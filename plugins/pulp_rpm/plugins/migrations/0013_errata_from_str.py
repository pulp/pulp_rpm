from pulp.server.db.connection import get_collection


def migrate(*args, **kwargs):
    """
    Migrate existing errata to have the key "from" instead of "from_str"
    """
    errata_collection = get_collection('units_erratum')
    rename_query = {'$rename': {'from_str': 'from'}}
    errata_collection.update({}, rename_query, safe=True, multi=True)
