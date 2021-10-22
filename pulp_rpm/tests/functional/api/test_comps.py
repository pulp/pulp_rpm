"""
Tests comps.xml upload functionality.
"""
from tempfile import NamedTemporaryFile

from pulpcore.client.pulp_rpm import (
    RepositoriesRpmApi,
    RepositoriesRpmVersionsApi,
    ContentPackagegroupsApi,
    ContentPackageenvironmentsApi,
    ContentPackagelangpacksApi,
    ContentPackagecategoriesApi,
    RpmCompsApi,
)

from pulp_rpm.tests.functional.constants import (
    BIG_COMPS_XML,
    BIG_CATEGORY,
    BIG_GROUPS,
    BIG_ENVIRONMENTS,
    BIG_LANGPACK,
    RPM_PACKAGEENVIRONMENT_CONTENT_NAME,
    RPM_PACKAGECATEGORY_CONTENT_NAME,
    RPM_PACKAGEGROUP_CONTENT_NAME,
    RPM_PACKAGELANGPACKS_CONTENT_NAME,
    SMALL_COMPS_XML,
    SMALL_CATEGORY,
    SMALL_ENVIRONMENTS,
    SMALL_GROUPS,
    SMALL_LANGPACK,
)
from pulp_rpm.tests.functional.utils import (
    gen_rpm_client,
)

from pulp_smash import api, config
from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    PulpTestCase,
)
from pulp_smash.pulp3.utils import gen_repo


class CompsXmlTestCase(PulpTestCase):
    """
    Test comps.xml-upload functionality.
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.rpm_client = gen_rpm_client()
        cls.comps_api = RpmCompsApi(cls.rpm_client)
        cls.repo_api = RepositoriesRpmApi(cls.rpm_client)
        cls.repo_version_api = RepositoriesRpmVersionsApi(cls.rpm_client)
        cls.groups_api = ContentPackagegroupsApi(cls.rpm_client)
        cls.envs_api = ContentPackageenvironmentsApi(cls.rpm_client)
        cls.groupslangpacks_api = ContentPackagelangpacksApi(cls.rpm_client)
        cls.categories_api = ContentPackagecategoriesApi(cls.rpm_client)
        cls.small_content = SMALL_GROUPS + SMALL_CATEGORY + SMALL_LANGPACK + SMALL_ENVIRONMENTS
        cls.centos8_content = BIG_GROUPS + BIG_CATEGORY + BIG_LANGPACK + BIG_ENVIRONMENTS

    def _upload_comps_into(self, file_path, expected_totals, repo_href=None, replace=False):
        data = {}
        if repo_href:
            data["repository"] = repo_href
            data["replace"] = replace
            expected_totals += 1
        response = self.comps_api.rpm_comps_upload(file=file_path, **data)
        task = monitor_task(response.task)
        rsrcs = task.created_resources
        self.assertEqual(expected_totals, len(rsrcs))
        return rsrcs

    def _eval_resources(self, resources, is_small=True):
        """Eval created_resources counts."""
        groups = [g for g in resources if "packagegroups" in g]
        self.assertEqual(len(groups), SMALL_GROUPS if is_small else BIG_GROUPS)

        categories = [g for g in resources if "packagecategories" in g]
        self.assertEqual(len(categories), SMALL_CATEGORY if is_small else BIG_CATEGORY)

        langpacks = [g for g in resources if "packagelangpacks" in g]
        self.assertEqual(len(langpacks), SMALL_LANGPACK if is_small else BIG_LANGPACK)

        envs = [g for g in resources if "environment" in g]
        self.assertEqual(len(envs), SMALL_ENVIRONMENTS if is_small else BIG_ENVIRONMENTS)

    def _eval_counts(self, summary, is_small=True):
        """Eval counts in a given summary."""
        for c in summary:
            if "rpm.packagegroup" in c:
                self.assertEquals(
                    summary["rpm.packagegroup"]["count"], SMALL_GROUPS if is_small else BIG_GROUPS
                )
            elif "rpm.packageenvironment" in c:
                self.assertEquals(
                    summary["rpm.packageenvironment"]["count"],
                    SMALL_ENVIRONMENTS if is_small else BIG_ENVIRONMENTS,
                )
            elif RPM_PACKAGECATEGORY_CONTENT_NAME in c:
                self.assertEquals(
                    summary[RPM_PACKAGECATEGORY_CONTENT_NAME]["count"],
                    SMALL_CATEGORY if is_small else BIG_CATEGORY,
                )
            elif "rpm.packagelangpacks" in c:
                self.assertEquals(
                    summary["rpm.packagelangpacks"]["count"],
                    SMALL_LANGPACK if is_small else BIG_LANGPACK,
                )

    def _eval_sum_counts(self, summary):
        """In a given summary, counts should be BIG+SMALL."""
        for c in summary:
            if RPM_PACKAGEGROUP_CONTENT_NAME in c:
                self.assertEquals(
                    summary[RPM_PACKAGEGROUP_CONTENT_NAME]["count"], (BIG_GROUPS + SMALL_GROUPS)
                )
            elif RPM_PACKAGEENVIRONMENT_CONTENT_NAME in c:
                self.assertEquals(
                    summary[RPM_PACKAGEENVIRONMENT_CONTENT_NAME]["count"],
                    (BIG_ENVIRONMENTS + SMALL_ENVIRONMENTS),
                )
            elif RPM_PACKAGECATEGORY_CONTENT_NAME in c:
                self.assertEquals(
                    summary[RPM_PACKAGECATEGORY_CONTENT_NAME]["count"],
                    (BIG_CATEGORY + SMALL_CATEGORY),
                )
            elif RPM_PACKAGELANGPACKS_CONTENT_NAME in c:
                self.assertEquals(
                    summary[RPM_PACKAGELANGPACKS_CONTENT_NAME]["count"],
                    (BIG_LANGPACK + SMALL_LANGPACK),
                )

    def setUp(self) -> None:
        """Set up a repo for us to upload into."""
        self.repo = self.repo_api.create(gen_repo())

    def tearDown(self) -> None:
        """Throw away the test repo and content."""
        self.repo_api.delete(self.repo.pulp_href)
        delete_orphans()

    def test_upload(self):
        """Upload a comps.xml and make sure it created comps-Content."""
        with NamedTemporaryFile("w+") as comps_file:
            comps_file.write(SMALL_COMPS_XML)
            comps_file.flush()
            resources = self._upload_comps_into(comps_file.name, self.small_content)
        self._eval_resources(resources)

    def test_upload_same(self):
        """Upload a comps.xml twice and make sure it doesn't create new objects the second time."""
        with NamedTemporaryFile("w+") as comps_file:
            comps_file.write(SMALL_COMPS_XML)
            comps_file.flush()
            first = self._upload_comps_into(comps_file.name, self.small_content)
            second = self._upload_comps_into(comps_file.name, self.small_content)

        # we return all resources in the comps.xml, even if they already existed
        self.assertEqual(sorted(first), sorted(second))

    def test_upload_diff(self):
        """Upload two different comps-files and make sure the second shows the new comps-Content."""
        with NamedTemporaryFile("w+") as comps_file:
            comps_file.write(SMALL_COMPS_XML)
            comps_file.flush()
            self._upload_comps_into(comps_file.name, self.small_content)
        with NamedTemporaryFile("w+") as comps_file:
            comps_file.write(BIG_COMPS_XML)
            comps_file.flush()
            second = self._upload_comps_into(comps_file.name, self.centos8_content)
        self._eval_resources(second, is_small=False)

    def test_upload_into_repo(self):
        """Upload comps into a repo and see new version created containing the comps-Content."""
        with NamedTemporaryFile("w+") as comps_file:
            comps_file.write(SMALL_COMPS_XML)
            comps_file.flush()
            resources = self._upload_comps_into(
                comps_file.name, self.small_content, self.repo.pulp_href
            )

        vers = [g for g in resources if "versions" in g]
        self.assertEqual(len(vers), 1)
        vers_resp = self.repo_version_api.read(vers[0])
        self.assertEqual(len(vers_resp.content_summary.added), 3)
        self.assertEqual(len(vers_resp.content_summary.present), 3)
        self._eval_counts(vers_resp.content_summary.added)

    def test_upload_into_repo_add(self):
        """Upload two comps-files into a repo and see the result being additive."""
        with NamedTemporaryFile("w+") as comps_file:
            comps_file.write(SMALL_COMPS_XML)
            comps_file.flush()
            resources = self._upload_comps_into(
                comps_file.name, self.small_content, self.repo.pulp_href
            )

        vers = [g for g in resources if "versions" in g]
        self.assertEqual(len(vers), 1)
        vers_resp = self.repo_version_api.read(vers[0])
        self.assertEqual(len(vers_resp.content_summary.added), 3)
        self.assertEqual(len(vers_resp.content_summary.present), 3)

        with NamedTemporaryFile("w+") as comps_file:
            comps_file.write(BIG_COMPS_XML)
            comps_file.flush()
            resources = self._upload_comps_into(
                comps_file.name, self.centos8_content, self.repo.pulp_href
            )
        vers = [g for g in resources if "versions" in g]
        self.assertEqual(len(vers), 1)
        vers_resp = self.repo_version_api.read(vers[0])
        self.assertEqual(vers_resp.number, 2)

        self.assertEqual(len(vers_resp.content_summary.added), 3)
        self.assertEqual(len(vers_resp.content_summary.present), 4)
        self._eval_counts(vers_resp.content_summary.added, is_small=False)
        self._eval_sum_counts(vers_resp.content_summary.present)

    def test_upload_into_repo_replace(self):
        """Upload two comps, see the comps-content from the second replace the existing."""
        with NamedTemporaryFile("w+") as comps_file:
            comps_file.write(SMALL_COMPS_XML)
            comps_file.flush()
            self._upload_comps_into(comps_file.name, self.small_content, self.repo.pulp_href)
        with NamedTemporaryFile("w+") as comps_file:
            comps_file.write(BIG_COMPS_XML)
            comps_file.flush()
            resources = self._upload_comps_into(
                comps_file.name, self.centos8_content, self.repo.pulp_href, True
            )
        vers = [g for g in resources if "versions" in g]
        self.assertEqual(len(vers), 1)
        vers_resp = self.repo_version_api.read(vers[0])
        self.assertEqual(vers_resp.number, 2)

        self.assertEqual(len(vers_resp.content_summary.added), 3)
        self.assertEqual(len(vers_resp.content_summary.present), 3)
        self._eval_counts(vers_resp.content_summary.added, is_small=False)
