"""Utilities for tests for the rpm plugin."""
import gzip
import os
import requests
import subprocess

from functools import partial
from io import StringIO
from unittest import SkipTest
from tempfile import NamedTemporaryFile

from pulp_smash import api, cli, config, selectors
from pulp_smash.pulp3.utils import gen_remote, get_content, require_pulp_3, require_pulp_plugins

from pulp_rpm.tests.functional.constants import (
    PRIVATE_GPG_KEY_URL,
    RPM_COPY_PATH,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_SIGNED_URL,
    RPM_UNSIGNED_FIXTURE_URL,
    RPM_PUBLICATION_PATH,
    PACKAGES_DIRECTORY,
)

from pulpcore.client.pulpcore import ApiClient as CoreApiClient, ArtifactsApi, TasksApi
from pulpcore.client.pulp_rpm import ApiClient as RpmApiClient


cfg = config.get_config()
configuration = cfg.get_bindings_config()


skip_if = partial(selectors.skip_if, exc=SkipTest)  # pylint:disable=invalid-name
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""

core_client = CoreApiClient(configuration)
tasks = TasksApi(core_client)


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulp_rpm isn't installed."""
    require_pulp_3(SkipTest)
    require_pulp_plugins({"rpm"}, SkipTest)


def gen_rpm_client():
    """Return an OBJECT for rpm client."""
    return RpmApiClient(configuration)


def gen_rpm_remote(url=RPM_UNSIGNED_FIXTURE_URL, **kwargs):
    """Return a semi-random dict for use in creating a rpm Remote.

    :param url: The URL of an external content source.
    """
    return gen_remote(url, **kwargs)


def get_rpm_package_paths(repo):
    """Return the relative path of content units present in a RPM repository.

    :param repo: A dict of information about the repository.
    :returns: A list with the paths of units present in a given repository.
    """
    return [
        content_unit["location_href"]
        for content_unit in get_content(repo)[RPM_PACKAGE_CONTENT_NAME]
        if "location_href" in content_unit
    ]


def gen_rpm_content_attrs(artifact, rpm_name):
    """Generate a dict with content unit attributes.

    :param artifact: A dict of info about the artifact.
    :returns: A semi-random dict for use in creating a content unit.
    """
    return {"artifact": artifact["pulp_href"], "relative_path": rpm_name}


def rpm_copy(cfg, config, recursive=False):
    """Sync a repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    :param remote: A dict of information about the remote of the repository
        to be synced.
    :param config: A dict of information about the copy.
    :param kwargs: Keyword arguments to be merged in to the request data.
    :returns: The server's response. A dict of information about the just
        created sync.
    """
    client = api.Client(cfg)
    data = {"config": config, "dependency_solving": recursive}
    return client.post(RPM_COPY_PATH, data)


def publish(cfg, repo, version_href=None, gpgcheck=0, repo_gpgcheck=0):
    """Publish a repository.

    :param pulp_smash.config.PulpSmashConfig cfg: Information about the Pulp
        host.
    :param repo: A dict of information about the repository.
    :param version_href: A href for the repo version to be published.
    :param gpgcheck: An option specifying whether to perform a GPG signature check on packages.
    :param repo_gpgcheck: An option specifying whether to perform a GPG signature check on
        the repodata.
    :returns: A publication. A dict of information about the just created
        publication.
    """
    if version_href:
        body = {"repository_version": version_href}
    else:
        body = {"repository": repo["pulp_href"]}

    body.update({"gpgcheck": gpgcheck, "repo_gpgcheck": repo_gpgcheck})

    client = api.Client(cfg, api.json_handler)
    call_report = client.post(RPM_PUBLICATION_PATH, body)
    tasks = tuple(api.poll_spawned_tasks(cfg, call_report))
    return client.get(tasks[-1]["created_resources"][0])


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
    kwargs.setdefault("name", name)
    kwargs.setdefault("baseurl", baseurl)
    # assume some common used defaults
    kwargs.setdefault("enabled", 1)
    kwargs.setdefault("gpgcheck", 0)
    kwargs.setdefault("metadata_expire", 0)  # force metadata load every time

    # Check if the settings specifies a content host role else assume ``api``
    try:
        content_host = cfg.get_hosts("content")[0].roles["content"]
    except IndexError:
        content_host = cfg.get_hosts("api")[0].roles["api"]

    # if sslverify is not provided in kwargs it is inferred from cfg
    kwargs.setdefault("sslverify", content_host.get("verify") and "yes" or "no")

    path = os.path.join("/etc/yum.repos.d/", repositoryid + ".repo")
    with StringIO() as section:
        section.write("[{}]\n".format(repositoryid))
        for key, value in kwargs.items():
            section.write("{} = {}\n".format(key, value))
        # machine.session is used here to keep SSH session open
        cli.Client(cfg).machine.session().run(
            'echo "{}" | {}tee {} > /dev/null'.format(
                section.getvalue(), "" if cli.is_root(cfg) else "sudo ", path
            )
        )
    return path


def gen_artifact(url=RPM_SIGNED_URL):
    """Creates an artifact."""
    response = requests.get(url)
    with NamedTemporaryFile() as temp_file:
        temp_file.write(response.content)
        temp_file.flush()
        artifact = ArtifactsApi(core_client).create(file=temp_file.name)
        return artifact.to_dict()


def init_signed_repo_configuration():
    """Initialize the configuration required for verifying a signed repository.

    This function downloads and imports a private GPG key by invoking subprocess
    commands. Then, it creates a new signing service on the fly.
    """
    # download the private key
    priv_key = subprocess.run(
        ("wget", "-q", "-O", "-", PRIVATE_GPG_KEY_URL), stdout=subprocess.PIPE
    ).stdout
    # import the downloaded private key
    subprocess.run(("gpg", "--import"), input=priv_key)

    # set the imported key to the maximum trust level
    key_fingerprint = "6EDF301256480B9B801EBA3D05A5E6DA269D9D98"
    completed_process = subprocess.run(("echo", f"{key_fingerprint}:6:"), stdout=subprocess.PIPE)
    subprocess.run(("gpg", "--import-ownertrust"), input=completed_process.stdout)

    # create a new signing service
    utils_dir_path = os.path.dirname(os.path.realpath(__file__))
    signing_script_path = os.path.join(utils_dir_path, "sign-metadata.sh")

    subprocess.run(
        (
            "pulpcore-manager",
            "add-signing-service",
            "sign-metadata",
            f"{signing_script_path}",
            "Pulp QE",
        )
    )


def get_package_repo_path(package_filename):
    """Get package repo path with directory structure.

    Args:
        package_filename(str): filename of RPM package

    Returns:
        (str): full path of RPM package in published repository

    """
    return os.path.join(PACKAGES_DIRECTORY, package_filename.lower()[0], package_filename)


def read_xml_gz(content):
    """
    Read xml and xml.gz.

    Tests work normally but fails for S3 due '.gz'
    Why is it only compressed for S3?
    """
    with NamedTemporaryFile() as temp_file:
        temp_file.write(content)
        temp_file.seek(0)

        try:
            content_xml = gzip.open(temp_file.name).read()
        except OSError:
            # FIXME: fix this as in CI primary/update_info.xml has '.gz' but it is not gzipped
            content_xml = temp_file.read()
        return content_xml
