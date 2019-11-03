# coding=utf-8
"""Verify whether package manager, yum/dnf, can consume content from Pulp."""
import unittest

from pulp_smash import api, cli, config
from pulp_smash.pulp3.constants import (
    ON_DEMAND_DOWNLOAD_POLICIES,
)
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_distribution,
    gen_repo,
    sync,
)

from pulp_rpm.tests.functional.utils import (
    gen_rpm_remote,
)
from pulp_rpm.tests.functional.constants import (
    RPM_DISTRIBUTION_PATH,
    RPM_REMOTE_PATH,
    RPM_REPO_PATH,
)
from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401
from pulp_rpm.tests.functional.utils import publish


class PackageManagerConsumeTestCase(unittest.TestCase):
    """Verify whether package manager can consume content from Pulp."""

    @classmethod
    def setUpClass(cls):
        """Verify whether dnf or yum are present."""
        cls.cfg = config.get_config()
        cls.pkg_mgr = cli.PackageManager(cls.cfg)
        cls.pkg_mgr.raise_if_unsupported(
            unittest.SkipTest,
            'This test requires dnf or yum.'
        )

    def test_on_demand_policies(self):
        """Verify whether content on demand synced can be consumed.

        This test targets the following issue:

        `Pulp #4496 <https://pulp.plan.io/issues/4496>`_
        """
        for policy in ON_DEMAND_DOWNLOAD_POLICIES:
            delete_orphans(self.cfg)
            self.do_test(policy)

    def test_immediate(self):
        """Verify whether package manager can consume content from Pulp.

        This test targets the following issue:

        `Pulp #3204 <https://pulp.plan.io/issues/3204>`_
        """
        self.do_test('immediate')

    def do_test(self, policy):
        """Verify whether package manager can consume content from Pulp."""
        client = api.Client(self.cfg, api.json_handler)
        body = gen_rpm_remote(policy=policy)
        remote = client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['pulp_href'])

        repo = client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['pulp_href'])

        sync(self.cfg, remote, repo)

        publication = publish(self.cfg, repo)
        self.addCleanup(client.delete, publication['pulp_href'])

        body = gen_distribution()
        body['publication'] = publication['pulp_href']
        distribution = client.using_handler(api.task_handler).post(
            RPM_DISTRIBUTION_PATH, body
        )
        self.addCleanup(client.delete, distribution['pulp_href'])

        cli_client = cli.Client(self.cfg)
        cli_client.run(('sudo', 'dnf', 'config-manager', '--add-repo', distribution['base_url']))
        repo_id = '*{}'.format(distribution['base_path'])
        cli_client.run(('sudo', 'dnf', 'config-manager', '--save',
                        '--setopt={}.gpgcheck=0'.format(repo_id), repo_id))
        self.addCleanup(cli_client.run, ('sudo', 'dnf', 'config-manager', '--disable', repo_id))
        rpm_name = 'walrus'
        self.pkg_mgr.install(rpm_name)
        self.addCleanup(self.pkg_mgr.uninstall, rpm_name)
        rpm = cli_client.run(('rpm', '-q', rpm_name)).stdout.strip().split('-')
        self.assertEqual(rpm_name, rpm[0])
