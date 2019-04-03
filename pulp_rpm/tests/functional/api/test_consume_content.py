# coding=utf-8
"""Verify whether package manager, yum/dnf, can consume content from Pulp."""
import unittest
from urllib.parse import urljoin

from pulp_smash import api, cli, config
from pulp_smash.exceptions import NoKnownPackageManagerError
from pulp_smash.pulp3.constants import DISTRIBUTION_PATH, REPO_PATH
from pulp_smash.pulp3.utils import (
    gen_distribution,
    gen_repo,
    publish,
    sync,
)

from pulp_rpm.tests.functional.utils import (
    gen_rpm_publisher,
    gen_rpm_remote,
)
from pulp_rpm.tests.functional.constants import (
    RPM_PUBLISHER_PATH,
    RPM_REMOTE_PATH,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401
from pulp_rpm.tests.functional.utils import gen_yum_config_file


class PackageManagerConsumeTestCase(unittest.TestCase):
    """Verify whether package manager can consume content from Pulp."""

    def test_all(self):
        """Verify whether package manager can consume content from Pulp.

        This test targets the following issue:

        `Pulp #3204 <https://pulp.plan.io/issues/3204>`_
        """
        cfg = config.get_config()
        pkg_mgr = cli.PackageManager(cfg)
        try:
            pkg_mgr.name
        except NoKnownPackageManagerError:
            raise unittest.SkipTest('This test requires dnf or yum.')
        client = api.Client(cfg, api.json_handler)
        body = gen_rpm_remote()
        remote = client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])

        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])

        sync(cfg, remote, repo)

        publisher = client.post(RPM_PUBLISHER_PATH, gen_rpm_publisher())
        self.addCleanup(client.delete, publisher['_href'])

        publication = publish(cfg, publisher, repo)
        self.addCleanup(client.delete, publication['_href'])

        body = gen_distribution()
        body['publication'] = publication['_href']
        distribution = client.using_handler(api.task_handler).post(
            DISTRIBUTION_PATH, body
        )
        self.addCleanup(client.delete, distribution['_href'])

        repo_path = gen_yum_config_file(
            cfg,
            baseurl=urljoin(
                cfg.get_content_host_base_url(),
                '//' + distribution['base_url']
            ),
            name=repo['name'],
            repositoryid=repo['name']
        )

        cli_client = cli.Client(cfg)
        self.addCleanup(cli_client.run, ('rm', repo_path), sudo=True)
        rpm_name = 'walrus'
        pkg_mgr.install(rpm_name)
        self.addCleanup(pkg_mgr.uninstall, rpm_name)
        rpm = cli_client.run(('rpm', '-q', rpm_name)).stdout.strip().split('-')
        self.assertEqual(rpm_name, rpm[0])
