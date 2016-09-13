"""
Migration for the new rendering system.
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

    # Escape all %
    for u in db.units_rpm.find():
        u["repodata"]["filelists"] = u["repodata"]["filelists"].replace("%", "%%")
        u["repodata"]["primary"] = u["repodata"]["primary"].replace("%", "%%")
        u["repodata"]["other"] = u["repodata"]["other"].replace("%", "%%")
        db.units_rpm.save(u)

    # Replace old django tags with new modulo ones
    db.eval("db.units_rpm.find().forEach(function(e,i) {"
            # filelists - {{ pkgid }}
            "e.repodata.filelists=e.repodata.filelists.replace("
            "'{{ pkgid }}','%(pkgid)s');"
            # primary - {{ checksum }} & {{ checksumtype }}
            "e.repodata.primary=e.repodata.primary.replace("
            "'{{ checksum }}','%(checksum)s').replace("
            "'{{ checksumtype }}','$(checksumtype)s');"
            # other - {{ pkgid }}
            "e.repodata.other=e.repodata.other.replace("
            "'{{ pkgid }}','%(pkgid)s');"
            "db.units_rpm.save(e);})"
            )
