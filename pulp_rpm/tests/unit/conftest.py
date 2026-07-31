import pytest
from django.db import connection


@pytest.fixture(autouse=True, scope="session")
def server_side_binding():
    """Enable server-side parameter binding for all unit tests, matching production."""
    opts = connection.settings_dict.setdefault("OPTIONS", {})
    original = opts.get("server_side_binding")
    opts["server_side_binding"] = True
    connection.close()
    yield
    if original is None:
        opts.pop("server_side_binding", None)
    else:
        opts["server_side_binding"] = original
    connection.close()
