# coding=utf-8
"""Utilities for tests for the rpm plugin."""
import os
from functools import partial
from io import StringIO
from unittest import SkipTest

from pulp_smash import api, cli, selectors
from pulp_smash.pulp3.utils import (
    gen_remote,
    gen_repo,
    get_content,
    require_pulp_3,
    require_pulp_plugins,
    sync,
)

from pulp_rpm.tests.functional.constants import (
    RPM_CONTENT_PATH,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_PUBLICATION_PATH,
    RPM_REMOTE_PATH,
    RPM_REPO_PATH,
    RPM_SIGNED_FIXTURE_URL,
    RPM_UNSIGNED_FIXTURE_URL,
)


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulp_rpm isn't installed."""
    require_pulp_3(SkipTest)
    require_pulp_plugins({'pulp_rpm'}, SkipTest)


def gen_rpm_remote(url=None, **kwargs):
    """Return a semi-random dict for use in creating a RPM remote.

    :param url: The URL of an external content source.
    """
    if url is None:
        url = RPM_UNSIGNED_FIXTURE_URL

    return gen_remote(url, **kwargs)


def get_rpm_package_paths(repo):
    """Return the relative path of content units present in a RPM repository.

    :param repo: A dict of information about the repository.
    :returns: A list with the paths of units present in a given repository.
    """
    return [
        content_unit['location_href']
        for content_unit in get_content(repo)[RPM_PACKAGE_CONTENT_NAME]
        if 'location_href' in content_unit
    ]


def populate_pulp(cfg, url=RPM_SIGNED_FIXTURE_URL):
    """Add RPM contents to Pulp.

    :param pulp_smash.config.PulpSmashConfig: Information about a Pulp
        application.
    :param url: The RPM repository URL. Defaults to
        :data:`pulp_smash.constants.RPM_UNSIGNED_FIXTURE_URL`
    :returns: A list of dicts, where each dict describes one RPM content in
        Pulp.
    """
    client = api.Client(cfg, api.json_handler)
    remote = {}
    repo = {}
    try:
        remote.update(client.post(RPM_REMOTE_PATH, gen_rpm_remote(url)))
        repo.update(client.post(RPM_REPO_PATH, gen_repo()))
        sync(cfg, remote, repo)
    finally:
        if remote:
            client.delete(remote['pulp_href'])
        if repo:
            client.delete(repo['pulp_href'])
    return client.get(RPM_CONTENT_PATH)['results']


def gen_yum_config_file(cfg, repositoryid, baseurl, name, **kwargs):
    """Generate a yum configuration file and write it to ``/etc/yum.repos.d/``.

    Generate a yum configuration file containing a single repository section,
    and write it to ``/etc/yum.repos.d/{repositoryid}.repo``.

    :param cfg: The system on which to create
        a yum configuration file.
    :param repositoryid: The section's ``repositoryid``. Used when naming the
        configuration file and populating the brackets at the head of the file.
        For details, see yum.conf(5).
    :param baseurl: The required option ``baseurl`` specifying the url of repo.
        For details, see yum.conf(5)
    :param name: The required option ``name`` specifying the name of repo.
        For details, see yum.conf(5).
    :param kwargs: Section options. Each kwarg corresponds to one option. For
        details, see yum.conf(5).
    :returns: The path to the yum configuration file.
    """
    # required repo options
    kwargs.setdefault('name', name)
    kwargs.setdefault('baseurl', baseurl)
    # assume some common used defaults
    kwargs.setdefault('enabled', 1)
    kwargs.setdefault('gpgcheck', 0)
    kwargs.setdefault('metadata_expire', 0)  # force metadata load every time

    # Check if the settings specifies a content host role else assume ``api``
    try:
        content_host = cfg.get_hosts('content')[0].roles['content']
    except IndexError:
        content_host = cfg.get_hosts('api')[0].roles['api']

    # if sslverify is not provided in kwargs it is inferred from cfg
    kwargs.setdefault(
        'sslverify', content_host.get('verify') and 'yes' or 'no'
    )

    path = os.path.join('/etc/yum.repos.d/', repositoryid + '.repo')
    with StringIO() as section:
        section.write('[{}]\n'.format(repositoryid))
        for key, value in kwargs.items():
            section.write('{} = {}\n'.format(key, value))
        # machine.session is used here to keep SSH session open
        cli.Client(cfg).machine.session().run(
            'echo "{}" | {}tee {} > /dev/null'.format(
                section.getvalue(),
                '' if cli.is_root(cfg) else 'sudo ',
                path
            )
        )
    return path


def publish(cfg, repo, version_href=None):
    """Publish a repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    :param repo: A dict of information about the repository.
    :param version_href: A href for the repo version to be published.
    :returns: A publication. A dict of information about the just created
        publication.
    """
    if version_href:
        body = {"repository_version": version_href}
    else:
        body = {"repository": repo["pulp_href"]}

    client = api.Client(cfg, api.json_handler)
    call_report = client.post(RPM_PUBLICATION_PATH, body)
    tasks = tuple(api.poll_spawned_tasks(cfg, call_report))
    return client.get(tasks[-1]["created_resources"][0])


skip_if = partial(selectors.skip_if, exc=SkipTest)
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""
