# coding=utf-8
"""Utilities for tests for the file plugin."""
from functools import partial
from unittest import SkipTest

from pulp_smash import selectors
from pulp_smash.pulp3.utils import (
    require_pulp_3,
    require_pulp_plugins,
)


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulp_rpm isn't installed."""
    require_pulp_3(SkipTest)
    require_pulp_plugins({'pulp_rpm'}, SkipTest)


skip_if = partial(selectors.skip_if, exc=SkipTest)
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""
