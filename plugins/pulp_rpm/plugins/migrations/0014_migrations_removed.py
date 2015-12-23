from pulp.server.db.migrate.models import MigrationRemovedError


def migrate(*args, **kwargs):
    raise MigrationRemovedError('0014', '2.8.0', '2.4.0', 'pulp_rpm')
