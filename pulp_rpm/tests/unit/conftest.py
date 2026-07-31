import pytest
from django.db import connection


@pytest.fixture
def server_side_binding():
    """Temporarily enable server-side parameter binding on the connection."""
    connection.ensure_connection()
    opts = connection.settings_dict.setdefault("OPTIONS", {})
    original = opts.get("server_side_binding")
    opts["server_side_binding"] = True
    yield
    if original is None:
        opts.pop("server_side_binding", None)
    else:
        opts["server_side_binding"] = original
