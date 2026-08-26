"""Unit tests for the comps.xml <-> Pulp model conversion layer.

These tests exercise a full round-trip: comps.xml -> rpmmd objects ->
Pulp content models (as they would be stored) -> rpmmd objects -> comps.xml,
using the production conversion functions from `app/comps.py`. They lock down
the corner cases documented in rpmrepo_metadata's
[docs/comps.md](https://github.com/dralley/rpmrepo_metadata/blob/master/docs/comps.md).

The API/DB/publish integration is covered separately by the functional tests;
here we isolate the pure translation logic.
"""

import rpmrepo_metadata as rpmmd
from django.test import TestCase

from pulp_rpm.app.comps import comps_to_model_dicts, models_to_comps_data
from pulp_rpm.app.models import (
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    PackageLangpacks,
)

# A comps document engineered to cover corner cases:
#   * name/description translations (xml:lang)
#   * every packagereq type (mandatory/default/optional/conditional)
#   * conditional `requires`
#   * `basearchonly="true"`
#   * `biarchonly` written only when true; a group with it false
#   * optional `display_order` (present on some, absent on others)
#   * empty packagelist and missing packagelist (both -> 0 packages)
#   * environment grouplist (mandatory) + optionlist with/without default
#   * category grouplist (UI only)
#   * langpacks with %{lang} placeholder
COMPS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE comps PUBLIC '-//Red Hat, Inc.//DTD Comps info//EN' 'comps.dtd'>
<comps>
  <group>
    <id>core</id>
    <name>Core</name>
    <name xml:lang="ja">コア</name>
    <description>Smallest possible installation.</description>
    <description xml:lang="ja">最小限のインストール</description>
    <default>true</default>
    <uservisible>true</uservisible>
    <biarchonly>false</biarchonly>
    <display_order>1</display_order>
    <packagelist>
      <packagereq type="mandatory">bash</packagereq>
      <packagereq type="default">vim-minimal</packagereq>
      <packagereq type="optional">zsh</packagereq>
      <packagereq type="conditional" requires="gtk3">ibus-gtk3</packagereq>
      <packagereq type="mandatory" basearchonly="true">grub2-efi-x64</packagereq>
    </packagelist>
  </group>
  <group>
    <id>i18n</id>
    <name>Serbian Support</name>
    <description>Language support.</description>
    <default>false</default>
    <uservisible>false</uservisible>
    <packagelist>
      <packagereq type="mandatory">glibc-langpack-sr</packagereq>
    </packagelist>
  </group>
  <group>
    <id>biarch</id>
    <name>Biarch</name>
    <description>Biarch only group.</description>
    <biarchonly>true</biarchonly>
    <packagelist>
      <packagereq type="default">glibc</packagereq>
    </packagelist>
  </group>
  <group>
    <id>empty-group-1</id>
    <name>Empty One</name>
    <description>Has an empty packagelist.</description>
    <packagelist>
    </packagelist>
  </group>
  <group>
    <id>empty-group-2</id>
    <name>Empty Two</name>
    <description>Has no packagelist at all.</description>
  </group>
  <category>
    <id>development</id>
    <name>Development</name>
    <name xml:lang="ja">開発</name>
    <description>Development tools.</description>
    <display_order>90</display_order>
    <grouplist>
      <groupid>core</groupid>
      <groupid>biarch</groupid>
    </grouplist>
  </category>
  <category>
    <id>servers</id>
    <name>Servers</name>
    <description>Server software.</description>
    <grouplist>
      <groupid>i18n</groupid>
    </grouplist>
  </category>
  <environment>
    <id>minimal</id>
    <name>Minimal Install</name>
    <name xml:lang="ja">最小限のインストール</name>
    <description>Basic functionality.</description>
    <display_order>3</display_order>
    <grouplist>
      <groupid>core</groupid>
    </grouplist>
    <optionlist>
      <groupid default="true">i18n</groupid>
      <groupid>biarch</groupid>
    </optionlist>
  </environment>
  <langpacks>
    <match name="firefox" install="firefox-langpacks-%{lang}"/>
    <match name="libreoffice-core" install="libreoffice-langpack-%{lang}"/>
  </langpacks>
</comps>
"""


def _models_from_comps(xml):
    """Parse comps XML and build (unsaved) Pulp content models from it.

    Uses the production conversion function `comps_to_model_dicts`.
    """
    comps = rpmmd.CompsData.from_xml(xml)
    group_dicts, category_dicts, environment_dicts, langpack_dict = comps_to_model_dicts(comps)

    groups = [PackageGroup(**gd) for gd in group_dicts]
    categories = [PackageCategory(**cd) for cd in category_dicts]
    environments = [PackageEnvironment(**ed) for ed in environment_dicts]
    langpacks = PackageLangpacks(**langpack_dict) if langpack_dict else None

    return comps, groups, categories, environments, langpacks


class TestCompsModelRoundtrip(TestCase):
    """comps.xml -> Pulp models -> comps.xml preserves all comps semantics."""

    def test_full_roundtrip_is_lossless(self):
        """The whole document survives a round-trip through the Pulp models."""
        original, groups, categories, environments, langpacks = _models_from_comps(COMPS_XML)
        rebuilt = models_to_comps_data(groups, categories, environments, langpacks)

        reparsed = rpmmd.CompsData.from_xml(rebuilt.to_xml())

        # Element ordering is not significant and is not preserved; canonicalize
        # both sides before comparing, and diff the dicts for a readable failure.
        original.canonicalize()
        reparsed.canonicalize()
        self.assertEqual(original.to_dict(), reparsed.to_dict())

    def _roundtrip_group(self, group_id):
        """Return the round-tripped rpmmd CompsGroup for a given group id."""
        _, groups, _, _, _ = _models_from_comps(COMPS_XML)
        by_id = {g.id: g for g in groups}
        return by_id[group_id].to_comps_group()

    def test_package_types_preserved(self):
        """All four packagereq types survive the round-trip."""
        group = self._roundtrip_group("core")
        by_name = {p.name: p for p in group.packages}
        self.assertEqual(by_name["bash"].reqtype, rpmmd.PackageReqType.MANDATORY)
        self.assertEqual(by_name["vim-minimal"].reqtype, rpmmd.PackageReqType.DEFAULT)
        self.assertEqual(by_name["zsh"].reqtype, rpmmd.PackageReqType.OPTIONAL)
        self.assertEqual(by_name["ibus-gtk3"].reqtype, rpmmd.PackageReqType.CONDITIONAL)

    def test_conditional_requires_preserved(self):
        """A conditional package keeps its `requires` target."""
        group = self._roundtrip_group("core")
        ibus = next(p for p in group.packages if p.name == "ibus-gtk3")
        self.assertEqual(ibus.requires, "gtk3")

    def test_basearchonly_preserved(self):
        """`basearchonly="true"` survives; absent normalized to false (continuity behavior, maybe change in the future)."""
        group = self._roundtrip_group("core")
        by_name = {p.name: p for p in group.packages}
        self.assertEqual(by_name["grub2-efi-x64"].basearchonly, True)
        self.assertFalse(by_name["bash"].basearchonly)

    def test_biarchonly_preserved(self):
        """`biarchonly` is preserved both when true and when false."""
        self.assertEqual(self._roundtrip_group("biarch").biarchonly, True)
        self.assertEqual(self._roundtrip_group("core").biarchonly, False)

    def test_display_order_optional(self):
        """`display_order` is preserved when set and None when absent."""
        self.assertEqual(self._roundtrip_group("core").display_order, 1)
        self.assertIsNone(self._roundtrip_group("i18n").display_order)

    def test_empty_and_missing_packagelist(self):
        """Both an empty and a missing packagelist yield zero packages."""
        self.assertEqual(len(self._roundtrip_group("empty-group-1").packages), 0)
        self.assertEqual(len(self._roundtrip_group("empty-group-2").packages), 0)

    def test_translations_preserved(self):
        """name/description xml:lang translations survive the round-trip."""
        group = self._roundtrip_group("core")
        self.assertEqual(group.name_by_lang.get("ja"), "コア")
        self.assertEqual(group.desc_by_lang.get("ja"), "最小限のインストール")

    def test_category_roundtrip(self):
        """Categories preserve their group list, translations, and display_order."""
        _, _, categories, _, _ = _models_from_comps(COMPS_XML)
        by_id = {c.to_comps_category().id: c.to_comps_category() for c in categories}

        development = by_id["development"]
        self.assertEqual(list(development.group_ids), ["core", "biarch"])
        self.assertEqual(development.display_order, 90)
        self.assertEqual(development.name_by_lang.get("ja"), "開発")

        # display_order is optional for categories too.
        self.assertIsNone(by_id["servers"].display_order)

    def test_environment_optionlist_defaults(self):
        """Environment optionlist entries preserve their `default` flag."""
        _, _, _, environments, _ = _models_from_comps(COMPS_XML)
        env = environments[0].to_comps_environment()

        self.assertEqual(env.id, "minimal")
        self.assertEqual(list(env.group_ids), ["core"])
        options = {opt.group_id: opt.default for opt in env.option_ids}
        self.assertEqual(options, {"i18n": True, "biarch": False})

    def test_langpacks_preserved(self):
        """Langpack match/install patterns survive the round-trip."""
        _, _, _, _, langpacks = _models_from_comps(COMPS_XML)
        self.assertEqual(
            langpacks.matches,
            {
                "firefox": "firefox-langpacks-%{lang}",
                "libreoffice-core": "libreoffice-langpack-%{lang}",
            },
        )


class TestCompsDigests(TestCase):
    """Digest calculation is deterministic and detects changes."""

    def test_digest_calculated_for_all_types(self):
        """All model types get a digest attribute from comps_to_model_dicts."""
        _, groups, categories, environments, langpacks = _models_from_comps(COMPS_XML)

        # All groups have digests
        for group in groups:
            self.assertIsNotNone(group.digest)
            self.assertEqual(len(group.digest), 64)  # SHA256 hex digest

        # All categories have digests
        for category in categories:
            self.assertIsNotNone(category.digest)
            self.assertEqual(len(category.digest), 64)

        # All environments have digests
        for environment in environments:
            self.assertIsNotNone(environment.digest)
            self.assertEqual(len(environment.digest), 64)

        # Langpacks has a digest
        self.assertIsNotNone(langpacks.digest)
        self.assertEqual(len(langpacks.digest), 64)

    def test_digest_detects_content_changes(self):
        """Different content produces different digests."""
        xml_modified = COMPS_XML.replace(
            "Smallest possible installation.", "A different description."
        )

        _, original_groups, _, _, _ = _models_from_comps(COMPS_XML)
        _, modified_groups, _, _, _ = _models_from_comps(xml_modified)

        original_core = next(g for g in original_groups if g.id == "core")
        modified_core = next(g for g in modified_groups if g.id == "core")

        # Same ID but different content -> different digest
        self.assertEqual(original_core.id, modified_core.id)
        self.assertNotEqual(original_core.digest, modified_core.digest)

    def test_known_static_digests(self):
        """Known digests for COMPS_XML items to detect unintentional algorithm changes.

        If this test fails after code changes, the digest algorithm may have changed
        unintentionally, which would break existing content deduplication in the DB.
        Only update these values if the change is intentional and you understand
        the migration impact.
        """
        _, groups, categories, environments, langpacks = _models_from_comps(COMPS_XML)

        # Known digests calculated from the COMPS_XML fixture
        KNOWN_DIGESTS = {
            "group:core": "b098917f95323f5161c28fff0035e7b239f28a9f9a9efb3e2ab3d5cf20219b1f",
            "group:i18n": "d288729a5b8b3dad3f945703f8d102064d9a2334c65999cf3ec6af0f41c98a69",
            "category:development": "c9f1bdafccbb6c85371408e10f0080784bef26d4beb2e3d6c74daa629ebd98e4",
            "environment:minimal": "f59e181354c89128d8a838bea22088bfec044f28fa769c15547ca83f31e782a8",
            "langpacks": "eed1c4b53c7e2af3e33fda022aaae987940b967e7a251930eab1e151e88d7968",
        }

        groups_by_id = {g.id: g for g in groups}
        self.assertEqual(groups_by_id["core"].digest, KNOWN_DIGESTS["group:core"])
        self.assertEqual(groups_by_id["i18n"].digest, KNOWN_DIGESTS["group:i18n"])

        categories_by_id = {c.id: c for c in categories}
        self.assertEqual(
            categories_by_id["development"].digest, KNOWN_DIGESTS["category:development"]
        )

        environments_by_id = {e.id: e for e in environments}
        self.assertEqual(environments_by_id["minimal"].digest, KNOWN_DIGESTS["environment:minimal"])

        self.assertEqual(langpacks.digest, KNOWN_DIGESTS["langpacks"])
