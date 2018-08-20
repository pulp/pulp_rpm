# coding=utf-8
"""Utilities for tests for the rpm plugin."""
from functools import partial
from unittest import SkipTest

from pulp_smash import api, selectors
from pulp_smash.pulp3.constants import (
    REPO_PATH
)
from pulp_smash.pulp3.utils import (
    gen_remote,
    gen_repo,
    gen_publisher,
    get_content,
    require_pulp_3,
    require_pulp_plugins,
    sync
)

from pulp_rpm.tests.functional.constants import (
    RPM_CONTENT_PATH,
    RPM_FIXTURE_URL,
    RPM_REMOTE_PATH,
)


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulp_rpm isn't installed."""
    require_pulp_3(SkipTest)
    require_pulp_plugins({'pulp_rpm'}, SkipTest)


def populate_pulp(cfg, url=RPM_FIXTURE_URL):
    """Add rpm contents to Pulp.

    :param pulp_smash.config.PulpSmashConfig: Information about a Pulp application.
    :param url: The rpm repository URL. Defaults to
        :data:`pulp_smash.constants.RPM_FIXTURE_URL`
    :returns: A list of dicts, where each dict describes one file content in Pulp.
    """
    client = api.Client(cfg, api.json_handler)
    remote = {}
    repo = {}
    try:
        remote.update(client.post(RPM_REMOTE_PATH, gen_rpm_remote(url)))
        repo.update(client.post(REPO_PATH, gen_repo()))
        sync(cfg, remote, repo)
    finally:
        if remote:
            client.delete(remote['_href'])
        if repo:
            client.delete(repo['_href'])
    return client.get(RPM_CONTENT_PATH)['results']


def gen_rpm_remote(**kwargs):
    """Return a semi-random dict for use in creating a rpm Remote.

    :param url: The URL of an external content source.
    """
    remote = gen_remote(RPM_FIXTURE_URL)
    rpm_extra_fields = {
        **kwargs
    }
    remote.update(rpm_extra_fields)
    return remote


def gen_rpm_publisher(**kwargs):
    """Return a semi-random dict for use in creating a Remote.

    :param url: The URL of an external content source.
    """
    publisher = gen_publisher()
    rpm_extra_fields = {
        **kwargs
    }
    publisher.update(rpm_extra_fields)
    return publisher


# FIXME: replace this boilerplate with a real implementation
def get_rpm_content_unit_paths(repo):
    """Return the relative path of content units present in a rpm repository.

    :param repo: A dict of information about the repository.
    :returns: A list with the paths of units present in a given repository.
    """
    # The "relative_path" is actually a file path and name
    return [content_unit['relative_path'] for content_unit in get_content(repo)]


skip_if = partial(selectors.skip_if, exc=SkipTest)
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""
