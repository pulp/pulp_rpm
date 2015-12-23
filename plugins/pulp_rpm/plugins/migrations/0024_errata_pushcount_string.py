"""
This migration casts the pushcount field as a String.

For the units_erratum collection, any object with the field 'pushcount' storing a non-String is
cast to a String and saved. This is required since non String values will not validate with the
Mongoengine definition. Any 'pushcount' fields which have the value null are unset.
"""
from pulp.server.db import connection


def migrate(*args, **kwargs):
    """
    Perform the migration as described in this module's docblock.

    :param args:   unused
    :type  args:   list
    :param kwargs: unused
    :type  kwargs: dict
    """
    db = connection.get_database()
    errata_collection = db['units_erratum']

    for erratum in errata_collection.find({'pushcount': {'$type': 10}}, {'pushcount': 1}):
        errata_collection.update({'_id': erratum['_id']}, {'$unset': {'pushcount': ""}})

    for erratum in errata_collection.find({'pushcount': {'$exists': True}}, {'pushcount': 1}):
        changed = False
        if not isinstance(erratum['pushcount'], basestring):
            if isinstance(erratum['pushcount'], float):
                erratum['pushcount'] = int(erratum['pushcount'])
            if isinstance(erratum['pushcount'], int):
                changed = True
                erratum['pushcount'] = str(erratum['pushcount'])
        if changed:
            errata_collection.update({'_id': erratum['_id']},
                                     {'$set': {'pushcount': erratum['pushcount']}})
