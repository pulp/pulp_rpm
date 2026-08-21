"""Unit tests for the comps.xml <-> Pulp model conversion layer.

These tests exercise a full round-trip: comps.xml -> rpmmd objects ->
Pulp content models (as they would be stored) -> rpmmd objects -> comps.xml,
mirroring the conversion done by ``parse_comps_components`` (upload/sync) and
the publish loop, but entirely in memory. They lock down the corner cases
documented in rpmrepo_metadata's ``docs/comps.md``.

The API/DB/publish integration is covered separately by the functional tests;
here we isolate the pure translation logic in ``models/comps.py``.
"""

import rpmrepo_metadata as rpmmd
from django.test import TestCase

from pulp_rpm.app.models import (
    PackageCategory,
    PackageEnvironment,
    PackageGroup,
    PackageLangpacks,
)

# A comps document engineered to cover the corner cases from docs/comps.md:
#   * name/description translations (xml:lang)
#   * every packagereq type (mandatory/default/optional/conditional)
#   * conditional `requires`
#   * `basearchonly="true"`
#   * `biarchonly` written only when true; a group with it false
#   * `langonly` restriction
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
    <langonly>sr</langonly>
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

    Mirrors ``parse_comps_components`` without touching the database.
    """
    comps = rpmmd.CompsData.from_xml(xml)
    groups = [PackageGroup(**PackageGroup.comps_to_dict(g)) for g in comps.groups]
    categories = [PackageCategory(**PackageCategory.comps_to_dict(c)) for c in comps.categories]
    environments = [
        PackageEnvironment(**PackageEnvironment.comps_to_dict(e)) for e in comps.environments
    ]
    langpacks = None
    if comps.langpacks:
        matches = PackageLangpacks.comps_to_dict(comps.langpacks)["matches"]
        langpacks = PackageLangpacks(matches=matches)
    return comps, groups, categories, environments, langpacks


def _comps_from_models(groups, categories, environments, langpacks):
    """Rebuild an rpmmd CompsData from Pulp content models.

    Mirrors the publish loop in ``tasks/publishing.py``.
    """
    comps = rpmmd.CompsData()
    comps.groups = [g.to_comps_group() for g in groups]
    comps.categories = [c.to_comps_category() for c in categories]
    comps.environments = [e.to_comps_environment() for e in environments]
    if langpacks is not None:
        comps.langpacks = [
            rpmmd.CompsLangpack(name=name, install=install)
            for name, install in langpacks.matches.items()
        ]
    return comps


class TestCompsModelRoundtrip(TestCase):
    """comps.xml -> Pulp models -> comps.xml preserves all comps semantics."""

    def test_full_roundtrip_is_lossless(self):
        """The whole document survives a round-trip through the Pulp models."""
        original, groups, categories, environments, langpacks = _models_from_comps(COMPS_XML)
        rebuilt = _comps_from_models(groups, categories, environments, langpacks)

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
        """`basearchonly="true"` survives; absent stays absent (None)."""
        group = self._roundtrip_group("core")
        by_name = {p.name: p for p in group.packages}
        self.assertEqual(by_name["grub2-efi-x64"].basearchonly, True)
        self.assertIsNone(by_name["bash"].basearchonly)

    def test_biarchonly_preserved(self):
        """`biarchonly` is preserved both when true and when false."""
        self.assertEqual(self._roundtrip_group("biarch").biarchonly, True)
        self.assertEqual(self._roundtrip_group("core").biarchonly, False)

    def test_langonly_preserved(self):
        """A group's `langonly` restriction survives; absent stays None."""
        self.assertEqual(self._roundtrip_group("i18n").langonly, "sr")
        self.assertIsNone(self._roundtrip_group("core").langonly)

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
