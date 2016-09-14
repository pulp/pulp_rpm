from pkgutil import extend_path

import django
from pulp.devel.unit.server import base as devel_base


__path__ = extend_path(__path__, __name__)

# prevent attempts to load the server conf during testing
devel_base.block_load_conf()


# The call to setup() happens automatically when a django app is started as a
# WSGI process. It also gets called automatically by celery during its
# initialization. Thus it only needs to be called by pulp when running unit
# tests. Some change in django 1.9 caused it to break when certain
# functionality was used before calling setup(), thus these two lines were
# added.
#
# https://pulp.plan.io/issues/2257
if django.VERSION >= (1, 9):
    django.setup()


def setup():
    """
    Set up the database connection for the tests to use.
    """
    devel_base.start_database_connection()


def teardown():
    """
    Drop the test database.
    """
    devel_base.drop_database()
