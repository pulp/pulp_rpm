# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software; if not,
# see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

from cStringIO import StringIO
import functools
import unittest
from xml.etree import ElementTree

from pulp_rpm.common import models
from pulp_rpm.plugins.importers.yum.repomd import group, packages


class TestProcessGroupElement(unittest.TestCase):
    def setUp(self):
        self.process_group = functools.partial(group.process_group_element, 'repo1')

    def test_fedora18_real_data(self):
        groups = packages.package_list_generator(StringIO(F18_COMPS_XML),
                                                 group.GROUP_TAG,
                                                 self.process_group)
        groups = list(groups)

        self.assertEqual(len(groups), 2)
        for model in groups:
            self.assertTrue(isinstance(model, models.PackageGroup))
            self.assertEqual(model.repo_id, 'repo1')
        self.assertFalse(groups[0].metadata['user_visible'])
        self.assertFalse(groups[0].metadata['default'])
        self.assertTrue(groups[1].metadata['user_visible'])
        self.assertFalse(groups[1].metadata['default'])

        # tests for fix to https://bugzilla.redhat.com/show_bug.cgi?id=1008010
        self.assertTrue(model.metadata['name'] in ['base-x', 'LibreOffice'],
                        'actual name: %s' % model.metadata['name'])
        self.assertTrue(len(groups[0].metadata['translated_description']) > 0)
        self.assertTrue(len(groups[0].metadata['translated_name']) > 0)

    def test_centos6_real_data(self):
        groups = packages.package_list_generator(StringIO(CENTOS6_COMPS_XML),
                                                 group.GROUP_TAG,
                                                 self.process_group)
        groups = list(groups)

        self.assertEqual(len(groups), 2)
        for model in groups:
            self.assertTrue(isinstance(model, models.PackageGroup))
            self.assertEqual(model.repo_id, 'repo1')

            # tests for fix to https://bugzilla.redhat.com/show_bug.cgi?id=1008010
            self.assertTrue(model.metadata['name'] in ['Afrikaans Support', 'Albanian Support'],
                            'actual name: %s' % model.metadata['name'])
            self.assertTrue(len(model.metadata['translated_name']) > 0)


class TestProcessCategoryElement(unittest.TestCase):
    def setUp(self):
        self.process_category = functools.partial(group.process_category_element, 'repo1')

    def test_fedora18_real_data(self):
        categories = packages.package_list_generator(StringIO(F18_COMPS_XML), group.CATEGORY_TAG,
                                                 self.process_category)
        categories = list(categories)

        self.assertEqual(len(categories), 1)
        self.assertTrue(isinstance(categories[0], models.PackageCategory))
        self.assertEqual(len(categories[0].metadata['packagegroupids']), 5)
        self.assertTrue('firefox' in categories[0].metadata['packagegroupids'])
        self.assertEqual(categories[0].id, 'gnome-desktop-environment')
        self.assertEqual(categories[0].repo_id, 'repo1')

        # tests for fix to https://bugzilla.redhat.com/show_bug.cgi?id=1008010
        self.assertEqual(categories[0].metadata['name'], 'GNOME Desktop')
        self.assertEqual(categories[0].metadata['description'],
                         '\nGNOME is a highly intuitive and user friendly desktop environment.\n')
        self.assertEqual(len(categories[0].metadata['translated_description']), 8)
        self.assertEqual(len(categories[0].metadata['translated_name']), 8)

    def test_centos6_real_data(self):
        categories = packages.package_list_generator(StringIO(CENTOS6_COMPS_XML), group.CATEGORY_TAG,
                                                 self.process_category)
        categories = list(categories)

        self.assertEqual(len(categories), 1)
        self.assertTrue(isinstance(categories[0], models.PackageCategory))
        self.assertEqual(categories[0].repo_id, 'repo1')
        self.assertEqual(len(categories[0].metadata['packagegroupids']), 26)
        self.assertTrue('network-tools' in categories[0].metadata['packagegroupids'])

        # tests for fix to https://bugzilla.redhat.com/show_bug.cgi?id=1008010
        self.assertEqual(categories[0].metadata['description'], 'Core system components.')
        self.assertEqual(categories[0].metadata['name'], 'Base System')
        self.assertEqual(len(categories[0].metadata['translated_description']), 25)
        self.assertEqual(len(categories[0].metadata['translated_name']), 58)
        self.assertEqual(categories[0].metadata['translated_name']['de'], 'Basissystem')


class TestProcessEnvironmentElement(unittest.TestCase):

    def setUp(self):
        self.process_environment = functools.partial(group.process_environment_element, 'repo1')

        self._build_base_group()

    def _build_base_group(self):
        env_element = ElementTree.Element('environment')
        ElementTree.SubElement(env_element, 'id').text = 'test-id'
        ElementTree.SubElement(env_element, 'display_order').text = '5'
        ElementTree.SubElement(env_element, 'name').text = 'foo-name'
        ElementTree.SubElement(env_element, 'description').text = 'foo-desc'
        group_list = ElementTree.SubElement(env_element, 'grouplist')
        ElementTree.SubElement(group_list, 'groupid').text = 'group1'
        ElementTree.SubElement(env_element, 'optionlist')

        self.element = env_element

    def test_minimal_set(self):
        group_model = self.process_environment(self.element)
        self.assertEquals(group_model.id, 'test-id')
        self.assertEquals(group_model.repo_id, 'repo1')
        self.assertEquals(group_model.metadata['display_order'], 5)
        self.assertEquals(group_model.metadata['name'], 'foo-name')
        self.assertEquals(group_model.metadata['description'], 'foo-desc')
        self.assertEquals(len(group_model.environment_groups), 1)
        self.assertEquals(group_model.environment_groups[0], 'group1')

    def test_translated_description(self):
        ElementTree.SubElement(self.element, 'description', {group.LANGUAGE_TAG: 'fr'}).text = 'desc2'
        ElementTree.SubElement(self.element, 'description', {group.LANGUAGE_TAG: 'es'}).text = 'desc3'

        group_model = self.process_environment(self.element)

        self.assertTrue('fr' in group_model.metadata['translated_description'])
        self.assertEquals(group_model.metadata['translated_description']['fr'], 'desc2')
        self.assertTrue('es' in group_model.metadata['translated_description'])
        self.assertEquals(group_model.metadata['translated_description']['es'], 'desc3')

    def test_translated_name(self):
        ElementTree.SubElement(self.element, 'name', {group.LANGUAGE_TAG: 'fr'}).text = 'name2'
        ElementTree.SubElement(self.element, 'name', {group.LANGUAGE_TAG: 'es'}).text = 'name3'

        group_model = self.process_environment(self.element)

        self.assertTrue('fr' in group_model.metadata['translated_name'])
        self.assertEquals(group_model.metadata['translated_name']['fr'], 'name2')
        self.assertTrue('es' in group_model.metadata['translated_name'])
        self.assertEquals(group_model.metadata['translated_name']['es'], 'name3')

    def test_group_list(self):
        group_element = self.element.find('grouplist')
        ElementTree.SubElement(group_element, 'groupid').text = 'group2'
        ElementTree.SubElement(group_element, 'groupid').text = 'group3'

        group_model = self.process_environment(self.element)

        self.assertEquals(len(group_model.environment_groups), 3)
        self.assertTrue('group1' in group_model.environment_groups)
        self.assertTrue('group2' in group_model.environment_groups)
        self.assertTrue('group3' in group_model.environment_groups)

    def test_option_list(self):
        group_element = self.element.find('optionlist')
        ElementTree.SubElement(group_element, 'groupid').text = 'group1'
        ElementTree.SubElement(group_element, 'groupid').text = 'group2'

        group_model = self.process_environment(self.element)

        self.assertEquals(len(group_model.environment_options), 2)
        self.assertTrue('group1' in group_model.environment_options)
        self.assertTrue('group2' in group_model.environment_options)

    def test_option_list_with_default(self):
        group_element = self.element.find('optionlist')
        ElementTree.SubElement(group_element, 'groupid', {'default': True}).text = 'group1'
        ElementTree.SubElement(group_element, 'groupid', {'default': True}).text = 'group2'

        group_model = self.process_environment(self.element)

        self.assertEquals(len(group_model.environment_default_options), 2)
        self.assertTrue('group1' in group_model.environment_default_options)
        self.assertTrue('group2' in group_model.environment_default_options)


# highly abridged version that grabs one group with a uservisible value
# and another without to make sure the default works.
F18_COMPS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" "comps.dtd">
<comps>
  <group>
    <id>base-x</id>
    <name>base-x</name>
    <name xml:lang="de">base-x</name>
    <name xml:lang="hu">base-x</name>
    <name xml:lang="ja">base-x</name>
    <name xml:lang="nl">basis-x</name>
    <name xml:lang="pl">base-x</name>
    <name xml:lang="uk">base-x</name>
    <name xml:lang="zh_TW">base-x</name>
    <description>Local X.org display server</description>
    <description xml:lang="de">Lokaler X.org-Displayserver</description>
    <description xml:lang="hu">Helyi X.org kijelző kiszolgáló</description>
    <description xml:lang="ja">ローカルのX.orgディスプレイサーバー</description>
    <description xml:lang="nl">Lokale X.org display server</description>
    <description xml:lang="pl">Lokalny serwer ekranu X.org</description>
    <description xml:lang="uk">Локальний графічний сервер X.org</description>
    <description xml:lang="zh_TW">本地端 X.rog 顯示伺服器</description>
    <default>false</default>
    <uservisible>false</uservisible>
    <packagelist>
      <packagereq>xorg-x11-drv-ati</packagereq>
      <packagereq>xorg-x11-drv-evdev</packagereq>
      <packagereq>xorg-x11-drv-fbdev</packagereq>
      <packagereq>xorg-x11-drv-geode</packagereq>
      <packagereq>xorg-x11-drv-intel</packagereq>
      <packagereq>xorg-x11-drv-mga</packagereq>
      <packagereq>xorg-x11-drv-modesetting</packagereq>
      <packagereq>xorg-x11-drv-nouveau</packagereq>
      <packagereq>xorg-x11-drv-omap</packagereq>
      <packagereq>xorg-x11-drv-openchrome</packagereq>
      <packagereq>xorg-x11-drv-qxl</packagereq>
      <packagereq>xorg-x11-drv-synaptics</packagereq>
      <packagereq>xorg-x11-drv-vesa</packagereq>
      <packagereq>xorg-x11-drv-vmmouse</packagereq>
      <packagereq>xorg-x11-drv-vmware</packagereq>
      <packagereq>xorg-x11-drv-wacom</packagereq>
      <packagereq>xorg-x11-server-Xorg</packagereq>
      <packagereq>xorg-x11-xauth</packagereq>
      <packagereq>xorg-x11-xinit</packagereq>
      <packagereq>glx-utils</packagereq>
      <packagereq>mesa-dri-drivers</packagereq>
      <packagereq>plymouth-system-theme</packagereq>
      <packagereq>spice-vdagent</packagereq>
      <packagereq>xorg-x11-utils</packagereq>
    </packagelist>
  </group>
  <group>
    <id>libreoffice</id>
    <name>LibreOffice</name>
    <name xml:lang="de">LibreOffice</name>
    <name xml:lang="hu">LibreOffice</name>
    <name xml:lang="ja">LibreOffice</name>
    <name xml:lang="nb">LibreOffice</name>
    <name xml:lang="nl">LibreOffice</name>
    <name xml:lang="pl">LibreOffice</name>
    <name xml:lang="uk">LibreOffice</name>
    <name xml:lang="zh_TW">LibreOffice</name>
    <description>LibreOffice Productivity Suite</description>
    <description xml:lang="de">LibreOffice-Suite</description>
    <description xml:lang="hu">LibreOffice Irodai alkalmazáscsomag</description>
    <description xml:lang="ja">LibreOffice 統合オフィススイート</description>
    <description xml:lang="nb">LibreOffice kontorstøtteprogramvare</description>
    <description xml:lang="nl">LibreOffice productiviteit suite</description>
    <description xml:lang="pl">Pakiet biurowy LibreOffice</description>
    <description xml:lang="uk">Комплект офісних програм LibreOffice</description>
    <description xml:lang="zh_TW">LibreOffice 生產力套裝軟體</description>
    <packagelist>
      <packagereq>libreoffice-calc</packagereq>
      <packagereq>libreoffice-draw</packagereq>
      <packagereq>libreoffice-graphicfilter</packagereq>
      <packagereq>libreoffice-impress</packagereq>
      <packagereq>libreoffice-math</packagereq>
      <packagereq>libreoffice-writer</packagereq>
      <packagereq>libreoffice-xsltfilter</packagereq>
    </packagelist>
  </group>
<category>
<id>gnome-desktop-environment</id>
<name>GNOME Desktop</name>
<name xml:lang="de">GNOME-Desktop</name>
<name xml:lang="hu">GNOME felület</name>
<name xml:lang="ja">GNOME デスクトップ</name>
<name xml:lang="nb">GNOME skrivebord</name>
<name xml:lang="nl">GNOME bureaublad</name>
<name xml:lang="pl">Środowisko GNOME</name>
<name xml:lang="uk">Графічне середовище GNOME</name>
<name xml:lang="zh_TW">GNOME 桌面</name>
<description>
GNOME is a highly intuitive and user friendly desktop environment.
</description>
<description xml:lang="de">
GNOME ist eine hoch-intuitive und benutzerfreundliche Benutzeroberfläche
</description>
<description xml:lang="hu">GNOME erősen intuitív és felhasználóbarát felület</description>
<description xml:lang="ja">GNOME は非常に直感的でユーザーフレンドリーなデスクトップ環境です。</description>
<description xml:lang="nb">
GNOME er et intuitivt og brukervennlig skrivebordsmiljø
</description>
<description xml:lang="nl">
GNOME is een heel intuïtieve en gebruikersvriendelijke bureaublad omgeving.
</description>
<description xml:lang="pl">
GNOME to intuicyjne i przyjazne dla użytkownika środowisko pulpitu.
</description>
<description xml:lang="uk">
GNOME — просте у користуванні та зручне графічне середовище.
</description>
<description xml:lang="zh_TW">GNOME 是相當直覺且友善的桌面環境。</description>
<display_order>5</display_order>
<grouplist>
<groupid>firefox</groupid>
<groupid>gnome-desktop</groupid>
<groupid>gnome-games</groupid>
<groupid>epiphany</groupid>
<groupid>libreoffice</groupid>
</grouplist>
</category>
</comps>
"""

# highly abridged version
CENTOS6_COMPS_XML = u"""<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE comps PUBLIC "-//CentOS//DTD Comps info//EN" "comps.dtd">
<comps>
  <group>
   <id>afrikaans-support</id>
   <name>Afrikaans Support</name>
   <name xml:lang='am'>የአፍሪካዊያን ድጋፍ</name>
   <name xml:lang='ar'>دعم الجنوب إفريقيّة</name>
   <name xml:lang='as'>আফ্ৰিক্যান্স সমৰ্থন</name>
   <name xml:lang='bal'>آپریکایی حمایت</name>
   <name xml:lang='bg'>Поддръжка на Африкаан</name>
   <name xml:lang='bn'>আফ্রিকান ভাষা ব্যবহারের সহায়তা</name>
   <name xml:lang='bn_IN'>আফ্রিকান ভাষা ব্যবহারের সহায়তা</name>
   <name xml:lang='bs'>Podrška za afrikaans</name>
   <name xml:lang='ca'>Suport per a l'afrikaans</name>
   <name xml:lang='cs'>Podpora afrikánštiny</name>
   <name xml:lang='da'>Understøttelse for afrikaans</name>
   <name xml:lang='de'>Unterstützung für Afrikaans</name>
   <name xml:lang='el'>Υποστήριξη Αφρικανικών</name>
   <name xml:lang='en_GB'>Afrikaans Support</name>
   <name xml:lang='es'>Soporte para africano</name>
   <name xml:lang='et'>afrikaansi keele toetus</name>
   <name xml:lang='fi'>Afrikaansin kielituki</name>
   <name xml:lang='fr'>Prise en charge de l'afrikaans</name>
   <name xml:lang='gu'>આફ્રિકાનો આધાર</name>
   <name xml:lang='he'>תמיכה באפריקנית</name>
   <name xml:lang='hi'>अफ्रीकी समर्थन</name>
   <name xml:lang='hr'>Podrška za afrikaans</name>
   <name xml:lang='hu'>Afrikaans nyelvi támogatás</name>
   <name xml:lang='id'>Dukungan Afrika</name>
   <name xml:lang='is'>Afríkanska</name>
   <name xml:lang='it'>Supporto Afrikaans</name>
   <name xml:lang='ja'>アフリカーンス語のサポート</name>
   <name xml:lang='kn'>ಆಫ್ರಿಕಾನಾಸ್ ಬೆಂಬಲ</name>
   <name xml:lang='ko'>아프리칸스어 지원</name>
   <name xml:lang='lv'>Āfrikāņu valodas atbalsts</name>
   <name xml:lang='mai'>अफ्रीकी समर्थन</name>
   <name xml:lang='mk'>Поддршка за африкански</name>
   <name xml:lang='ml'>ആഫ്രിക്കന്‍സ് പിന്തുണ</name>
   <name xml:lang='mr'>आफ्रीकी समर्थन</name>
   <name xml:lang='ms'>Sokongan Afrikaan</name>
   <name xml:lang='nb'>Støtte for Afrikaans</name>
   <name xml:lang='ne'>अफ्रिकी समर्थन</name>
   <name xml:lang='nl'>Ondersteuning voor Afrikaans</name>
   <name xml:lang='no'>Støtte for Afrikaans</name>
   <name xml:lang='or'>ଆଫ୍ରାକୀୟ ସହାୟତା</name>
   <name xml:lang='pa'>ਅਫਰੀਕੀ ਸਹਿਯੋਗ</name>
   <name xml:lang='pl'>Obsługa afrykanerskiego</name>
   <name xml:lang='pt'>Suporte a Afrikaans</name>
   <name xml:lang='pt_BR'>Suporte à Afrikaans</name>
   <name xml:lang='ro'>Suport pentru africană</name>
   <name xml:lang='ru'>Поддержка Африкаанс</name>
   <name xml:lang='si'>ඇෆ්රිකාන්ස් භාශා පහසුකම</name>
   <name xml:lang='sk'>Juhoafrická podpora</name>
   <name xml:lang='sl'>Afrikanška podpora</name>
   <name xml:lang='sr'>Подршка за африкански</name>
   <name xml:lang='sr@latin'>Podrška za afrikanski</name>
   <name xml:lang='sr@Latn'>Podrška za afrikanski</name>
   <name xml:lang='sv'>Stöd för afrikaans</name>
   <name xml:lang='ta'>ஆப்ரிக்க துணை</name>
   <name xml:lang='te'>ఆఫ్రికాన్‌ల మద్దతు</name>
   <name xml:lang='tg'>Пуштибонии забони африкоӣ</name>
   <name xml:lang='th'>Afrikaans Support</name>
   <name xml:lang='tr'>Afrikanca Desteği</name>
   <name xml:lang='uk'>Підтримка Африканс</name>
   <name xml:lang='ur'>افریقہ ساتھ</name>
   <name xml:lang='zh_CN'>南非荷兰语支持</name>
   <name xml:lang='zh_TW'>南非荷蘭語支援</name>
   <description/>
   <default>false</default>
   <uservisible>true</uservisible>
   <langonly>af</langonly>
   <packagelist>
      <packagereq requires="autocorr-en" type="conditional">autocorr-af</packagereq>
      <packagereq requires="hyphen" type="conditional">hyphen-af</packagereq>
      <packagereq requires="libreoffice-core" type="conditional">libreoffice-langpack-af</packagereq>
   </packagelist>
  </group>
  <group>
   <id>albanian-support</id>
   <name>Albanian Support</name>
   <name xml:lang='as'>আল্বানিয়ান ভাষাৰ সমৰ্থন</name>
   <name xml:lang='bal'>آلبانیایی حمایت</name>
   <name xml:lang='bg'>Поддръжка на Албански</name>
   <name xml:lang='bn'>আলবেনিয়ান ভাষা ব্যবহারের সহায়তা</name>
   <name xml:lang='bn_IN'>আলবেনিয়ান ভাষা ব্যবহারের সহায়তা</name>
   <name xml:lang='ca'>Suport per a l'albanès</name>
   <name xml:lang='cs'>Podpora albánštiny</name>
   <name xml:lang='da'>Understøttelse af albansk</name>
   <name xml:lang='de'>Unterstützung für Albanisch</name>
   <name xml:lang='el'>Υποστήριξη Αλβανικών</name>
   <name xml:lang='es'>Soporte para albanés</name>
   <name xml:lang='et'>Albaania keele tugi</name>
   <name xml:lang='fi'>Albanian kielituki</name>
   <name xml:lang='fr'>Prise en charge de l'albanais</name>
   <name xml:lang='gu'>અલ્બેનિયાઈ આધાર</name>
   <name xml:lang='he'>תמיכה באלבנית</name>
   <name xml:lang='hi'>अल्बानियाई समर्थन</name>
   <name xml:lang='hu'>Albán támogatás</name>
   <name xml:lang='id'>Dukungan Albania</name>
   <name xml:lang='is'>Albönska</name>
   <name xml:lang='it'>Supporto lingua albanese</name>
   <name xml:lang='ja'>アルバニア語のサポート</name>
   <name xml:lang='kn'>ಅಲ್ಬೇನಿಯನ್ ಬೆಂಬಲ</name>
   <name xml:lang='ko'>알바니아어 지원</name>
   <name xml:lang='lv'>Albāņu valodas atbalsts</name>
   <name xml:lang='mai'>अल्बानियाइ समर्थन</name>
   <name xml:lang='ml'>അല്‍ബേനിയന്‍ പിന്തുണ</name>
   <name xml:lang='mr'>अलबेनीयन समर्थन</name>
   <name xml:lang='nb'>Støtte for albansk</name>
   <name xml:lang='ne'>अल्बानियाली समर्थन</name>
   <name xml:lang='nl'>Ondersteuning voor Albanees</name>
   <name xml:lang='or'>ଆଲବାନିୟାନ ସହାୟତା</name>
   <name xml:lang='pa'>ਅਲਬਾਨੀਅਨ ਸਹਿਯੋਗ</name>
   <name xml:lang='pl'>Obsługa albańskiego</name>
   <name xml:lang='pt'>Suporte a Albanês</name>
   <name xml:lang='pt_BR'>Suporte à Albanês</name>
   <name xml:lang='ru'>Поддержка албанского языка</name>
   <name xml:lang='sk'>Albánska podpora</name>
   <name xml:lang='sr'>Подршка за албански</name>
   <name xml:lang='sr@latin'>Podrška za albanski</name>
   <name xml:lang='sr@Latn'>Podrška za albanski</name>
   <name xml:lang='sv'>Stöd för albanska</name>
   <name xml:lang='ta'>அல்பேனியன் துணை</name>
   <name xml:lang='te'>అల్బేనియన్ మద్దతు</name>
   <name xml:lang='tg'>Пуштибонии забони албаниявӣ</name>
   <name xml:lang='th'>การสนับสนุนภาษาแอลเบเนีย</name>
   <name xml:lang='uk'>Підтримка албанської</name>
   <name xml:lang='zh_CN'>阿尔巴尼亚语支持</name>
   <name xml:lang='zh_TW'>阿爾班尼亞語支援</name>
   <description/>
   <default>false</default>
   <uservisible>true</uservisible>
   <langonly>sq</langonly>
   <packagelist>
   	          <packagereq requires="eclipse-platform" type="conditional">eclipse-nls-sq</packagereq>
      <packagereq requires="hunspell" type="conditional">hunspell-sq</packagereq>
   </packagelist>
  </group>
  <category>
   <id>base-system</id>
   <name>Base System</name>
   <name xml:lang='as'>ভিত্তি চিস্টেম</name>
   <name xml:lang='bal'>سیستم پایه</name>
   <name xml:lang='bg'>Базова система</name>
   <name xml:lang='bn'>মৌলিক সিস্টেম</name>
   <name xml:lang='bn_IN'>মৌলিক সিস্টেম</name>
   <name xml:lang='bs'>Osnovni sistem</name>
   <name xml:lang='ca'>Sistema bàsic</name>
   <name xml:lang='cs'>Základ systému</name>
   <name xml:lang='da'>Basesystem</name>
   <name xml:lang='de'>Basissystem</name>
   <name xml:lang='el'>Βασικό σύστημα</name>
   <name xml:lang='en_GB'>Base System</name>
   <name xml:lang='es'>Sistema Base</name>
   <name xml:lang='et'>Põhisüsteem</name>
   <name xml:lang='fi'>Perusjärjestelmä</name>
   <name xml:lang='fr'>Système de base</name>
   <name xml:lang='gu'>આધાર સિસ્ટમ</name>
   <name xml:lang='he'>מערכת בסיס</name>
   <name xml:lang='hi'>बेस सिस्टम</name>
   <name xml:lang='hr'>Osnovni sustav</name>
   <name xml:lang='hu'>Alaprendszer</name>
   <name xml:lang='id'>Sistem Dasar</name>
   <name xml:lang='is'>Grunnkerfið</name>
   <name xml:lang='it'>Sistema base</name>
   <name xml:lang='ja'>ベースシステム</name>
   <name xml:lang='kn'>ಮೂಲ ವ್ಯವಸ್ಥೆ</name>
   <name xml:lang='ko'>기반 시스템</name>
   <name xml:lang='lv'>Pamatsistēma</name>
   <name xml:lang='mai'>बेस सिस्टम</name>
   <name xml:lang='ml'>ബെയിസ് സിസ്റ്റം</name>
   <name xml:lang='mr'>आधार प्रणाली</name>
   <name xml:lang='ms'>Sistem Asas</name>
   <name xml:lang='nb'>Basissystem</name>
   <name xml:lang='ne'>आधार प्रणाली</name>
   <name xml:lang='nl'>Basissysteem</name>
   <name xml:lang='or'>ମୌଳିକ ତନ୍ତ୍ର</name>
   <name xml:lang='pa'>ਮੁੱਢਲਾ ਸਿਸਟਮ</name>
   <name xml:lang='pl'>Podstawowy system</name>
   <name xml:lang='pt'>Sistema de Base</name>
   <name xml:lang='pt_BR'>Sistema Básico</name>
   <name xml:lang='ro'>Sistem de bază</name>
   <name xml:lang='ru'>Базовая система</name>
   <name xml:lang='si'>මූලික පද්ධතිය</name>
   <name xml:lang='sk'>Základ systému</name>
   <name xml:lang='sl'>Osnovni sistem</name>
   <name xml:lang='sq'>Sistem Bazë</name>
   <name xml:lang='sr'>Основни систем</name>
   <name xml:lang='sr@latin'>Osnovni sistem</name>
   <name xml:lang='sr@Latn'>Osnovni sistem</name>
   <name xml:lang='sv'>Bassystem</name>
   <name xml:lang='ta'>அடிப்படை அமைப்பு</name>
   <name xml:lang='te'>ఆధార వ్యవస్థ</name>
   <name xml:lang='tg'>Асосҳои системавӣ</name>
   <name xml:lang='th'>ระบบพื้นฐาน</name>
   <name xml:lang='tr'>Temel Sistem</name>
   <name xml:lang='uk'>Базова система</name>
   <name xml:lang='zh_CN'>基本系统</name>
   <name xml:lang='zh_TW'>基礎系統</name>
   <description>Core system components.</description>
   <description xml:lang='as'>প্ৰণালীৰ মূখ্য সামগ্ৰী।</description>
   <description xml:lang='bn'>সিস্টেমের কোর সামগ্রী।</description>
   <description xml:lang='bn_IN'>সিস্টেমের কোর সামগ্রী।</description>
   <description xml:lang='de'>Zentrale Systemkomponenten.</description>
   <description xml:lang='es'>Componentes de sistema Core</description>
   <description xml:lang='fr'>Composants du système de base.</description>
   <description xml:lang='gu'>કોર સિસ્ટમ સાધનો.</description>
   <description xml:lang='hi'>प्रधान सिस्टम घटक</description>
   <description xml:lang='it'>Componenti di base del sistema.</description>
   <description xml:lang='ja'>コアシステムコンポーネント</description>
   <description xml:lang='kn'>ಪ್ರಮುಖ ವ್ಯವಸ್ಥೆಯ ಘಟಕಗಳು.</description>
   <description xml:lang='ko'>핵심 시스템 콤포넌트.</description>
   <description xml:lang='ml'>കോര്‍ സിസ്റ്റം ഘടകങ്ങള്‍.</description>
   <description xml:lang='mr'>कोर प्रणाली घटके.</description>
   <description xml:lang='or'>ମୂଖ୍ୟ ତନ୍ତ୍ର ଉପାଦାନଗୁଡ଼ିକ।</description>
   <description xml:lang='pa'>ਮੁੱਖ ਸਿਸਟਮ ਹਿੱਸੇ।</description>
   <description xml:lang='pl'>Główne składniki systemu.</description>
   <description xml:lang='pt_BR'>Componentes de sistema central</description>
   <description xml:lang='ru'>Основные компоненты системы.</description>
   <description xml:lang='sv'>Grundläggande systemkomponenter.</description>
   <description xml:lang='ta'>உள்ளீடு கணினி ஆக்கக்கூறுகள்.</description>
   <description xml:lang='te'>కోర్ సిస్టమ్ మూలకములు.</description>
   <description xml:lang='uk'>Основні компонент систем.</description>
   <description xml:lang='zh_CN'>核系统组件。</description>
   <description xml:lang='zh_TW'>核心系統元件。</description>
   <grouplist>
    <groupid>backup-client</groupid>
    <groupid>base</groupid>
    <groupid>client-mgmt-tools</groupid>
    <groupid>compat-libraries</groupid>
    <groupid>console-internet</groupid>
    <groupid>debugging</groupid>
    <groupid>dial-up</groupid>
    <groupid>directory-client</groupid>
    <groupid>java-platform</groupid>
    <groupid>legacy-unix</groupid>
    <groupid>mainframe-access</groupid>
    <groupid>network-file-system-client</groupid>
    <groupid>network-tools</groupid>
    <groupid>performance</groupid>
    <groupid>perl-runtime</groupid>
    <groupid>print-client</groupid>
    <groupid>ruby-runtime</groupid>
    <groupid>security-tools</groupid>
    <groupid>smart-card</groupid>
    <groupid>hardware-monitoring</groupid>
    <groupid>infiniband</groupid>
    <groupid>large-systems</groupid>
    <groupid>scientific</groupid>
    <groupid>storage-client-fcoe</groupid>
    <groupid>storage-client-iscsi</groupid>
    <groupid>storage-client-multipath</groupid>
   </grouplist>
  </category>
</comps>
""".encode('utf8')
