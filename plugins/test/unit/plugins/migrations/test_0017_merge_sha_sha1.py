"""
This module contains unit tests for pulp_rpm.plugins.migrations.0017_merge_sha_sha1.py.
"""
import unittest

from pulp.server.db.migrate.models import _import_all_the_way
from pymongo import collection, errors
import mock

migration = _import_all_the_way('pulp_rpm.plugins.migrations.0017_merge_sha_sha1')


SUMLESS_ERRATA = [
    {u'issued': u'2012-01-27 16:08:06', u'references': [], u'_content_type_id': u'erratum',
     u'id': u'RHEA-2012:0002', u'from': u'errata@redhat.com', u'severity': u'',
     u'title': u'Sea_Erratum', u'_ns': u'units_erratum', u'version': u'1',
     u'reboot_suggested': True, u'type': u'security',
     u'pkglist': [
         {u'packages': [
             {u'src': u'http://www.fedoraproject.org', u'name': u'walrus', u'sum': None,
              u'filename': u'walrus-0.71-1.noarch.rpm', u'epoch': u'0', u'version': u'0.71',
              u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'},
             {u'src': u'http://www.fedoraproject.org', u'name': u'penguin', u'sum': None,
              u'filename': u'penguin-0.9.1-1.noarch.rpm', u'epoch': u'0', u'version': u'0.9.1',
              u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'},
             {u'src': u'http://www.fedoraproject.org', u'name': u'shark', u'sum': None,
              u'filename': u'shark-0.1-1.noarch.rpm', u'epoch': u'0', u'version': u'0.1',
              u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'}],
          u'name': u'1', u'short': u''}],
     u'status': u'stable', u'updated': u'', u'description': u'Sea_Erratum',
     u'_last_updated': 1416857488, u'pushcount': u'', u'_storage_path': None, u'rights': u'',
     u'solution': u'', u'summary': u'', u'release': u'1',
     u'_id': u'2e56d875-ff44-45ee-84ff-7840e957872d'},
    {u'issued': u'2012-01-27 16:08:05', u'references': [], u'_content_type_id': u'erratum',
     u'id': u'RHEA-2012:0001', u'from': u'errata@redhat.com', u'severity': u'',
     u'title': u'Bear_Erratum', u'_ns': u'units_erratum', u'version': u'1',
     u'reboot_suggested': True, u'type': u'security',
     u'pkglist': [
         {u'packages': [
            {u'src': u'http://www.fedoraproject.org', u'name': u'bear', u'sum': None,
             u'filename': u'bear-4.1-1.noarch.rpm', u'epoch': u'0', u'version': u'4.1',
             u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'}],
          u'name': u'1', u'short': u''}],
     u'status': u'stable', u'updated': u'', u'description': u'Bear_Erratum',
     u'_last_updated': 1416857488, u'pushcount': u'', u'_storage_path': None, u'rights': u'',
     u'solution': u'', u'summary': u'', u'release': u'1',
     u'_id': u'87a0ee80-d421-40be-985a-ba0db51e27f5'}]

# This example data contains one package reference that uses SHA.
SHA_ERRATA = [
    {u'issued': u'2012-01-27 16:08:06', u'references': [], u'_content_type_id': u'erratum',
     u'id': u'RHEA-2012:0002', u'from': u'errata@redhat.com', u'severity': u'',
     u'title': u'Sea_Erratum', u'_ns': u'units_erratum', u'version': u'1',
     u'reboot_suggested': True, u'type': u'security',
     u'pkglist': [
         {u'packages': [
             {u'src': u'http://www.fedoraproject.org', u'name': u'walrus', u'sum': None,
              u'filename': u'walrus-0.71-1.noarch.rpm', u'epoch': u'0', u'version': u'0.71',
              u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'},
             {u'src': u'http://www.fedoraproject.org', u'name': u'penguin', u'sum': None,
              u'filename': u'penguin-0.9.1-1.noarch.rpm', u'epoch': u'0', u'version': u'0.9.1',
              u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'},
             {u'src': u'http://www.fedoraproject.org', u'name': u'shark', u'sum': None,
              u'filename': u'shark-0.1-1.noarch.rpm', u'epoch': u'0', u'version': u'0.1',
              u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'}],
          u'name': u'1', u'short': u''}],
     u'status': u'stable', u'updated': u'', u'description': u'Sea_Erratum',
     u'_last_updated': 1416857488, u'pushcount': u'', u'_storage_path': None, u'rights': u'',
     u'solution': u'', u'summary': u'', u'release': u'1',
     u'_id': u'2e56d875-ff44-45ee-84ff-7840e957872d'},
    {u'issued': u'2012-01-27 16:08:05', u'references': [], u'_content_type_id': u'erratum',
     u'id': u'RHEA-2012:0001', u'from': u'errata@redhat.com', u'severity': u'',
     u'title': u'Bear_Erratum', u'_ns': u'units_erratum', u'version': u'1',
     u'reboot_suggested': True, u'type': u'security',
     u'pkglist': [
         {u'packages': [
            {u'src': u'http://www.fedoraproject.org', u'name': u'bear',
             u'sum': ['SHA', 'some checksum'],
             u'filename': u'bear-4.1-1.noarch.rpm', u'epoch': u'0', u'version': u'4.1',
             u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'}],
          u'name': u'1', u'short': u''}],
     u'status': u'stable', u'updated': u'', u'description': u'Bear_Erratum',
     u'_last_updated': 1416857488, u'pushcount': u'', u'_storage_path': None, u'rights': u'',
     u'solution': u'', u'summary': u'', u'release': u'1',
     u'_id': u'87a0ee80-d421-40be-985a-ba0db51e27f5'}]

# This example data contains one package reference that uses SHA-1.
SHA1_ERRATA = [
    {u'issued': u'2012-01-27 16:08:06', u'references': [], u'_content_type_id': u'erratum',
     u'id': u'RHEA-2012:0002', u'from': u'errata@redhat.com', u'severity': u'',
     u'title': u'Sea_Erratum', u'_ns': u'units_erratum', u'version': u'1',
     u'reboot_suggested': True, u'type': u'security',
     u'pkglist': [
         {u'packages': [
             {u'src': u'http://www.fedoraproject.org', u'name': u'walrus', u'sum': None,
              u'filename': u'walrus-0.71-1.noarch.rpm', u'epoch': u'0', u'version': u'0.71',
              u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'},
             {u'src': u'http://www.fedoraproject.org', u'name': u'penguin', u'sum': None,
              u'filename': u'penguin-0.9.1-1.noarch.rpm', u'epoch': u'0', u'version': u'0.9.1',
              u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'},
             {u'src': u'http://www.fedoraproject.org', u'name': u'shark', u'sum': None,
              u'filename': u'shark-0.1-1.noarch.rpm', u'epoch': u'0', u'version': u'0.1',
              u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'}],
          u'name': u'1', u'short': u''}],
     u'status': u'stable', u'updated': u'', u'description': u'Sea_Erratum',
     u'_last_updated': 1416857488, u'pushcount': u'', u'_storage_path': None, u'rights': u'',
     u'solution': u'', u'summary': u'', u'release': u'1',
     u'_id': u'2e56d875-ff44-45ee-84ff-7840e957872d'},
    {u'issued': u'2012-01-27 16:08:05', u'references': [], u'_content_type_id': u'erratum',
     u'id': u'RHEA-2012:0001', u'from': u'errata@redhat.com', u'severity': u'',
     u'title': u'Bear_Erratum', u'_ns': u'units_erratum', u'version': u'1',
     u'reboot_suggested': True, u'type': u'security',
     u'pkglist': [
         {u'packages': [
            {u'src': u'http://www.fedoraproject.org', u'name': u'bear',
             u'sum': ['sha1', 'some checksum'],
             u'filename': u'bear-4.1-1.noarch.rpm', u'epoch': u'0', u'version': u'4.1',
             u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'}],
          u'name': u'1', u'short': u''}],
     u'status': u'stable', u'updated': u'', u'description': u'Bear_Erratum',
     u'_last_updated': 1416857488, u'pushcount': u'', u'_storage_path': None, u'rights': u'',
     u'solution': u'', u'summary': u'', u'release': u'1',
     u'_id': u'87a0ee80-d421-40be-985a-ba0db51e27f5'}]

# This example data contains one package reference that uses SHA-1 capitalized. This should become
# lowercase.
CAPITALIZED_SHA1_ERRATA = [
    {u'issued': u'2012-01-27 16:08:06', u'references': [], u'_content_type_id': u'erratum',
     u'id': u'RHEA-2012:0002', u'from': u'errata@redhat.com', u'severity': u'',
     u'title': u'Sea_Erratum', u'_ns': u'units_erratum', u'version': u'1',
     u'reboot_suggested': True, u'type': u'security',
     u'pkglist': [
         {u'packages': [
             {u'src': u'http://www.fedoraproject.org', u'name': u'walrus', u'sum': None,
              u'filename': u'walrus-0.71-1.noarch.rpm', u'epoch': u'0', u'version': u'0.71',
              u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'},
             {u'src': u'http://www.fedoraproject.org', u'name': u'penguin', u'sum': None,
              u'filename': u'penguin-0.9.1-1.noarch.rpm', u'epoch': u'0', u'version': u'0.9.1',
              u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'},
             {u'src': u'http://www.fedoraproject.org', u'name': u'shark', u'sum': None,
              u'filename': u'shark-0.1-1.noarch.rpm', u'epoch': u'0', u'version': u'0.1',
              u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'}],
          u'name': u'1', u'short': u''}],
     u'status': u'stable', u'updated': u'', u'description': u'Sea_Erratum',
     u'_last_updated': 1416857488, u'pushcount': u'', u'_storage_path': None, u'rights': u'',
     u'solution': u'', u'summary': u'', u'release': u'1',
     u'_id': u'2e56d875-ff44-45ee-84ff-7840e957872d'},
    {u'issued': u'2012-01-27 16:08:05', u'references': [], u'_content_type_id': u'erratum',
     u'id': u'RHEA-2012:0001', u'from': u'errata@redhat.com', u'severity': u'',
     u'title': u'Bear_Erratum', u'_ns': u'units_erratum', u'version': u'1',
     u'reboot_suggested': True, u'type': u'security',
     u'pkglist': [
         {u'packages': [
            {u'src': u'http://www.fedoraproject.org', u'name': u'bear',
             u'sum': ['SHA1', 'some checksum'],
             u'filename': u'bear-4.1-1.noarch.rpm', u'epoch': u'0', u'version': u'4.1',
             u'release': u'1', u'reboot_suggested': u'False', u'arch': u'noarch'}],
          u'name': u'1', u'short': u''}],
     u'status': u'stable', u'updated': u'', u'description': u'Bear_Erratum',
     u'_last_updated': 1416857488, u'pushcount': u'', u'_storage_path': None, u'rights': u'',
     u'solution': u'', u'summary': u'', u'release': u'1',
     u'_id': u'87a0ee80-d421-40be-985a-ba0db51e27f5'}]

CAPITALIZED_RPM = {
    "_content_type_id": "rpm", "_id": "c0038e92-505f-46a8-a8d1-d6fe710604f6",
    "_last_updated": 1417539208, "_ns": "units_rpm",
    "_storage_path": "/var/lib/pulp/content/rpm/bear/4.1/1/noarch/"
                     "7a831f9f90bf4d21027572cb503d20b702de8e8785b02c0397445c2e481d81b3/"
                     "bear-4.1-1.noarch.rpm",
    "arch": "noarch", "build_time": 1331831374, "buildhost": "smqe-ws15", "changelog": [],
    "checksum": "7a831f9f90bf4d21027572cb503d20b702de8e8785b02c0397445c2e481d81b3",
    "checksum_type": None, "checksumtype": "SHA256", "description": "A dummy package of bear",
    "epoch": "0", "filelist": ["/tmp/bear.txt"], "filename": "bear-4.1-1.noarch.rpm",
    "files": {"dir": [], "file": ["/tmp/bear.txt"]}, "group": "Internet/Applications",
    "header_range": {"start": 872, "end": 2289}, "license": "GPLv2", "name": "bear",
    "provides": [{"release": "1", "epoch": "0",  "version": "4.1",  "flags": "EQ",
                  "name": "bear"}],
    "relative_url_path": None, "relativepath": "bear-4.1-1.noarch.rpm", "release": "1",
    "release_sort_index": "01-1",
    "repodata": {
        "filelists": "\n<package pkgid="
                     "\"7a831f9f90bf4d21027572cb503d20b702de8e8785b02c0397445c2e481d81b3\" "
                     "name=\"bear\" arch=\"noarch\">\n  <version epoch=\"0\" ver=\"4.1\" "
                     "rel=\"1\"/>\n  <file>/tmp/bear.txt</file>\n</package>",
        "other": "\n<package pkgid="
                 "\"7a831f9f90bf4d21027572cb503d20b702de8e8785b02c0397445c2e481d81b3\" "
                 "name=\"bear\" arch=\"noarch\">\n  <version epoch=\"0\" ver=\"4.1\" rel=\"1\"/>\n"
                 "</package>",
        "primary": "\n<package type=\"rpm\">\n  <name>bear</name>\n  <arch>noarch</arch>\n  "
                   "<version epoch=\"0\" ver=\"4.1\" rel=\"1\"/>\n  <checksum type=\"sha256\" "
                   "pkgid=\"YES\">7a831f9f90bf4d21027572cb503d20b702de8e8785b02c0397445c2e481d81b3"
                   "</checksum>\n  <summary>A dummy package of bear</summary>\n  <description>A "
                   "dummy package of bear</description>\n  <packager></packager>\n  "
                   "<url>http://tstrachota.fedorapeople.org</url>\n  <time file=\"1416877948\" "
                   "build=\"1331831374\"/>\n  <size package=\"2438\" installed=\"42\" "
                   "archive=\"296\"/>\n  <location href=\"bear-4.1-1.noarch.rpm\"/>\n  <format>\n "
                   "<rpm:license>GPLv2</rpm:license>\n    <rpm:vendor/>\n    "
                   "<rpm:group>Internet/Applications</rpm:group>\n    "
                   "<rpm:buildhost>smqe-ws15</rpm:buildhost>\n    "
                   "<rpm:sourcerpm>bear-4.1-1.src.rpm</rpm:sourcerpm>\n    "
                   "<rpm:header-range start=\"872\" end=\"2289\"/>\n    <rpm:provides>\n      "
                   "<rpm:entry name=\"bear\" flags=\"EQ\" epoch=\"0\" ver=\"4.1\" rel=\"1\"/>\n   "
                   "</rpm:provides>\n  </format>\n</package>"},
        "requires": [], "size": 2438, "sourcerpm": "bear-4.1-1.src.rpm",
        "summary": "A dummy package of bear", "time": 1331832453,
        "url": "http://tstrachota.fedorapeople.org", "vendor": None, "version": "4.1",
        "version_sort_index": "01-4.01-1"}

SHA_RPM = {
    "_content_type_id": "rpm", "_id": "c0038e92-505f-46a8-a8d1-d6fe710604f7",
    "_last_updated": 1417539208, "_ns": "units_rpm",
    "_storage_path": "/var/lib/pulp/content/rpm/bear/4.1/1/noarch/"
                     "7cc8894d84696bfac328a0f7104daec7cbb0f5c4/"
                     "bear-4.1-1.noarch.rpm",
    "arch": "noarch", "build_time": 1331831374, "buildhost": "smqe-ws15", "changelog": [],
    "checksum": "7cc8894d84696bfac328a0f7104daec7cbb0f5c4",
    "checksum_type": None, "checksumtype": "sha", "description": "A dummy package of bear",
    "epoch": "0", "filelist": ["/tmp/bear.txt"], "filename": "bear-4.1-1.noarch.rpm",
    "files": {"dir": [], "file": ["/tmp/bear.txt"]}, "group": "Internet/Applications",
    "header_range": {"start": 872, "end": 2289}, "license": "GPLv2", "name": "bear",
    "provides": [{"release": "1", "epoch": "0",  "version": "4.1",  "flags": "EQ",
                  "name": "bear"}],
    "relative_url_path": None, "relativepath": "bear-4.1-1.noarch.rpm", "release": "1",
    "release_sort_index": "01-1",
    "repodata": {
        "filelists": "\n<package pkgid="
                     "\"7cc8894d84696bfac328a0f7104daec7cbb0f5c4\" "
                     "name=\"bear\" arch=\"noarch\">\n  <version epoch=\"0\" ver=\"4.1\" "
                     "rel=\"1\"/>\n  <file>/tmp/bear.txt</file>\n</package>",
        "other": "\n<package pkgid="
                 "\"7cc8894d84696bfac328a0f7104daec7cbb0f5c4\" "
                 "name=\"bear\" arch=\"noarch\">\n  <version epoch=\"0\" ver=\"4.1\" rel=\"1\"/>\n"
                 "</package>",
        "primary": "\n<package type=\"rpm\">\n  <name>bear</name>\n  <arch>noarch</arch>\n  "
                   "<version epoch=\"0\" ver=\"4.1\" rel=\"1\"/>\n  <checksum type=\"sha\" "
                   "pkgid=\"YES\">7cc8894d84696bfac328a0f7104daec7cbb0f5c4"
                   "</checksum>\n  <summary>A dummy package of bear</summary>\n  <description>A "
                   "dummy package of bear</description>\n  <packager></packager>\n  "
                   "<url>http://tstrachota.fedorapeople.org</url>\n  <time file=\"1416877948\" "
                   "build=\"1331831374\"/>\n  <size package=\"2438\" installed=\"42\" "
                   "archive=\"296\"/>\n  <location href=\"bear-4.1-1.noarch.rpm\"/>\n  <format>\n "
                   "<rpm:license>GPLv2</rpm:license>\n    <rpm:vendor/>\n    "
                   "<rpm:group>Internet/Applications</rpm:group>\n    "
                   "<rpm:buildhost>smqe-ws15</rpm:buildhost>\n    "
                   "<rpm:sourcerpm>bear-4.1-1.src.rpm</rpm:sourcerpm>\n    "
                   "<rpm:header-range start=\"872\" end=\"2289\"/>\n    <rpm:provides>\n      "
                   "<rpm:entry name=\"bear\" flags=\"EQ\" epoch=\"0\" ver=\"4.1\" rel=\"1\"/>\n   "
                   "</rpm:provides>\n  </format>\n</package>"},
        "requires": [], "size": 2438, "sourcerpm": "bear-4.1-1.src.rpm",
        "summary": "A dummy package of bear", "time": 1331832453,
        "url": "http://tstrachota.fedorapeople.org", "vendor": None, "version": "4.1",
        "version_sort_index": "01-4.01-1"}

SHA1_RPM = {
    "_content_type_id": "rpm", "_id": "c0038e92-505f-46a8-a8d1-d6fe710604f8",
    "_last_updated": 1417539208, "_ns": "units_rpm",
    "_storage_path": "/var/lib/pulp/content/rpm/bear/4.1/1/noarch/"
                     "7cc8894d84696bfac328a0f7104daec7cbb0f5c4/"
                     "bear-4.1-1.noarch.rpm",
    "arch": "noarch", "build_time": 1331831374, "buildhost": "smqe-ws15", "changelog": [],
    "checksum": "7cc8894d84696bfac328a0f7104daec7cbb0f5c4",
    "checksum_type": None, "checksumtype": "sha1", "description": "A dummy package of bear",
    "epoch": "0", "filelist": ["/tmp/bear.txt"], "filename": "bear-4.1-1.noarch.rpm",
    "files": {"dir": [], "file": ["/tmp/bear.txt"]}, "group": "Internet/Applications",
    "header_range": {"start": 872, "end": 2289}, "license": "GPLv2", "name": "bear",
    "provides": [{"release": "1", "epoch": "0",  "version": "4.1",  "flags": "EQ",
                  "name": "bear"}],
    "relative_url_path": None, "relativepath": "bear-4.1-1.noarch.rpm", "release": "1",
    "release_sort_index": "01-1",
    "repodata": {
        "filelists": "\n<package pkgid="
                     "\"7cc8894d84696bfac328a0f7104daec7cbb0f5c4\" "
                     "name=\"bear\" arch=\"noarch\">\n  <version epoch=\"0\" ver=\"4.1\" "
                     "rel=\"1\"/>\n  <file>/tmp/bear.txt</file>\n</package>",
        "other": "\n<package pkgid="
                 "\"7cc8894d84696bfac328a0f7104daec7cbb0f5c4\" "
                 "name=\"bear\" arch=\"noarch\">\n  <version epoch=\"0\" ver=\"4.1\" rel=\"1\"/>\n"
                 "</package>",
        "primary": "\n<package type=\"rpm\">\n  <name>bear</name>\n  <arch>noarch</arch>\n  "
                   "<version epoch=\"0\" ver=\"4.1\" rel=\"1\"/>\n  <checksum type=\"sha1\" "
                   "pkgid=\"YES\">7cc8894d84696bfac328a0f7104daec7cbb0f5c4"
                   "</checksum>\n  <summary>A dummy package of bear</summary>\n  <description>A "
                   "dummy package of bear</description>\n  <packager></packager>\n  "
                   "<url>http://tstrachota.fedorapeople.org</url>\n  <time file=\"1416877948\" "
                   "build=\"1331831374\"/>\n  <size package=\"2438\" installed=\"42\" "
                   "archive=\"296\"/>\n  <location href=\"bear-4.1-1.noarch.rpm\"/>\n  <format>\n "
                   "<rpm:license>GPLv2</rpm:license>\n    <rpm:vendor/>\n    "
                   "<rpm:group>Internet/Applications</rpm:group>\n    "
                   "<rpm:buildhost>smqe-ws15</rpm:buildhost>\n    "
                   "<rpm:sourcerpm>bear-4.1-1.src.rpm</rpm:sourcerpm>\n    "
                   "<rpm:header-range start=\"872\" end=\"2289\"/>\n    <rpm:provides>\n      "
                   "<rpm:entry name=\"bear\" flags=\"EQ\" epoch=\"0\" ver=\"4.1\" rel=\"1\"/>\n   "
                   "</rpm:provides>\n  </format>\n</package>"},
        "requires": [], "size": 2438, "sourcerpm": "bear-4.1-1.src.rpm",
        "summary": "A dummy package of bear", "time": 1331832453,
        "url": "http://tstrachota.fedorapeople.org", "vendor": None, "version": "4.1",
        "version_sort_index": "01-4.01-1"}

CAPITALIZED_YUM_METADATA_FILE = [
    {"_id": "912e27dd-2bff-489f-9b81-9c5425554d65",
     "_storage_path": "/var/lib/pulp/content/yum_repo_metadata_file/rhel7/productid.gz",
     "repo_id": "rhel7", "data_type": "productid",
     "checksum": "83c44bfabdcea3cc17c3fe98f222ac12719e7af5", "_last_updated": 1414528243,
     "_content_type_id": "yum_repo_metadata_file", "checksum_type": "SHA256",
     "_ns": "units_yum_repo_metadata_file"}]

SHA_YUM_METADATA_FILE = [
    {"_id": "912e27dd-2bff-489f-9b81-9c5425554d65",
     "_storage_path": "/var/lib/pulp/content/yum_repo_metadata_file/rhel7/productid.gz",
     "repo_id": "rhel7", "data_type": "productid",
     "checksum": "83c44bfabdcea3cc17c3fe98f222ac12719e7af5", "_last_updated": 1414528243,
     "_content_type_id": "yum_repo_metadata_file", "checksum_type": "sha",
     "_ns": "units_yum_repo_metadata_file"}]

SHA1_YUM_METADATA_FILE = [
    {"_id": "912e27dd-2bff-489f-9b81-9c5425554d65",
     "_storage_path": "/var/lib/pulp/content/yum_repo_metadata_file/rhel7/productid.gz",
     "repo_id": "rhel7", "data_type": "productid",
     "checksum": "83c44bfabdcea3cc17c3fe98f222ac12719e7af5", "_last_updated": 1414528243,
     "_content_type_id": "yum_repo_metadata_file", "checksum_type": "sha1",
     "_ns": "units_yum_repo_metadata_file"}]


class TestMigrate(unittest.TestCase):
    """
    Test the migrate() function.
    """
    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1._migrate_errata',
                side_effect=migration._migrate_errata)
    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1._migrate_rpmlike_units',
                side_effect=migration._migrate_rpmlike_units)
    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1._migrate_yum_metadata_files',
                side_effect=migration._migrate_yum_metadata_files)
    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_calls_correct_functions(self, get_collection, _migrate_yum_metadata_files,
                                     _migrate_rpmlike_units, _migrate_errata):
        """
        Assert that migrate() calls the correct other functions that do the real work.
        """
        migration.migrate()

        # _migrate_rpmlike_units() should have been called three times, once each for 'rpm', 'drpm',
        # and 'srpm'.
        self.assertEqual(_migrate_rpmlike_units.call_count, 3)
        expected_args = set(('rpm', 'drpm', 'srpm'))
        actual_args = set([c[1][0] for c in _migrate_rpmlike_units.mock_calls])
        self.assertEqual(actual_args, expected_args)
        # The other two types should each have been called once
        _migrate_yum_metadata_files.assert_called_once_with()
        _migrate_errata.assert_called_once_with()


class TestMigrateErratum(unittest.TestCase):
    """
    This class contains tests for the _migrate_errata() function.
    """
    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_no_sum(self, get_collection):
        """
        All real-world errata that I could find did not have anything in the "sum" field,
        curiously. This test ensures that we handle that scenario accurately.
        """
        errata = mock.MagicMock(spec=collection.Collection)
        errata.find.return_value = SUMLESS_ERRATA
        get_collection.return_value = errata

        migration._migrate_errata()

        get_collection.assert_called_once_with('units_erratum')
        # Since there were no sums, there should have been 0 calls to errata.update
        self.assertEqual(errata.update.call_count, 0)

    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_with_capitalized_sha1(self, get_collection):
        """
        Test with a package reference that uses "SHA1" as the type. This should get corrected to
        "sha1".
        """
        errata = mock.MagicMock(spec=collection.Collection)
        errata.find.return_value = CAPITALIZED_SHA1_ERRATA
        get_collection.return_value = errata

        migration._migrate_errata()

        get_collection.assert_called_once_with('units_erratum')
        # We expect one call to update to set the checksum to "sha1"
        errata.update.assert_called_once_with(
            {'_id': '87a0ee80-d421-40be-985a-ba0db51e27f5'},
            {'$set': {
                'pkglist': [
                    {u'packages': [
                        {u'src': u'http://www.fedoraproject.org', u'epoch': u'0',
                         u'version': u'4.1', u'name': u'bear', u'release': u'1',
                         u'sum': ['sha1', 'some checksum'], u'reboot_suggested': u'False',
                         u'arch': u'noarch', u'filename': u'bear-4.1-1.noarch.rpm'}],
                     u'name': u'1', u'short': u''}]}})

    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_with_sha(self, get_collection):
        """
        All real-world errata that I could find did not have anything in the "sum" field,
        curiously. This test ensures that we handle the mysterious scenario where errata have "SHA"
        as a sum so the sum needs to be corrected.
        """
        errata = mock.MagicMock(spec=collection.Collection)
        errata.find.return_value = SHA_ERRATA
        get_collection.return_value = errata

        migration._migrate_errata()

        get_collection.assert_called_once_with('units_erratum')
        # We expect one call to update to set the checksum to "sha1"
        errata.update.assert_called_once_with(
            {'_id': '87a0ee80-d421-40be-985a-ba0db51e27f5'},
            {'$set': {
                'pkglist': [
                    {u'packages': [
                        {u'src': u'http://www.fedoraproject.org', u'epoch': u'0',
                         u'version': u'4.1', u'name': u'bear', u'release': u'1',
                         u'sum': ['sha1', 'some checksum'], u'reboot_suggested': u'False',
                         u'arch': u'noarch', u'filename': u'bear-4.1-1.noarch.rpm'}],
                     u'name': u'1', u'short': u''}]}})

    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_with_sha1_erratum(self, get_collection):
        """
        This test ensures that checksum types that are already sanitized get left alone.
        """
        errata = mock.MagicMock(spec=collection.Collection)
        errata.find.return_value = SHA1_ERRATA
        get_collection.return_value = errata

        migration._migrate_errata()

        get_collection.assert_called_once_with('units_erratum')
        # Since there were no incorrect sum types, there should have been 0 calls to erratum.update.
        self.assertEqual(errata.update.call_count, 0)


class TestMigrateRPMlikeUnits(unittest.TestCase):
    """
    This class contains tests for _migrate_rpmlike_units().
    """
    def _generate_get_collection_mock(self):
        def get_collection(collection_name):
            if collection_name not in ('repos', 'repo_content_units', 'units_rpm'):
                raise ValueError("No unit test in this test class should try to get a collection "
                                 "that is not in the above tuple.")
            attribute_name = '_mock_%s_collection' % collection_name
            try:
                return getattr(self, attribute_name)
            except AttributeError:
                collection = mock.MagicMock()
                setattr(self, attribute_name, collection)
                return collection
        return get_collection

    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_capitalized(self, get_collection):
        """
        Test correct behavior when the checksum type is capitalized.
        """
        get_collection.side_effect = self._generate_get_collection_mock()
        self._mock_units_rpm_collection = mock.MagicMock(collection.Collection)
        self._mock_units_rpm_collection.find.return_value = [CAPITALIZED_RPM]

        migration._migrate_rpmlike_units('rpm')

        # get_collection() should have been called three times, once for each of repos,
        # repo_content_units, and units_rpm.
        self.assertEqual(get_collection.call_count, 3)
        self.assertEqual(set([c[1] for c in get_collection.mock_calls]),
                         set([('repos',), ('repo_content_units',), ('units_rpm',)]))
        # Since the RPM's checksumtype was SHA256, we should have seen a call to update it to
        # sha256.
        self._mock_units_rpm_collection.update.assert_called_once_with(
            {'_id': 'c0038e92-505f-46a8-a8d1-d6fe710604f6'}, {'$set': {'checksumtype': 'sha256'}})
        # Since we were able to update the checksum type successfully, no calls should have been
        # made to any of the following methods
        self.assertEqual(self._mock_units_rpm_collection.find_one.call_count, 0)
        self.assertEqual(self._mock_repo_content_units_collection.find.call_count, 0)
        self.assertEqual(self._mock_repo_content_units_collection.update.call_count, 0)
        self.assertEqual(self._mock_repo_content_units_collection.remove.call_count, 0)
        self.assertEqual(self._mock_repos_collection.update.call_count, 0)
        self.assertEqual(self._mock_units_rpm_collection.remove.call_count, 0)

    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_duplicate_rpm_and_duplicate_rcu(self, get_collection):
        """
        Test for the case when there is a duplicate RPM and there is a duplicate in the
        repo_content_units collection. This would happen if the SHA and SHA1 version of the same
        package were found in the same repo.
        """
        get_collection.side_effect = self._generate_get_collection_mock()
        self._mock_units_rpm_collection = mock.MagicMock(collection.Collection)
        self._mock_units_rpm_collection.find.return_value = [SHA_RPM, SHA1_RPM]
        self._mock_units_rpm_collection.find_one.return_value = SHA1_RPM
        # This will cause a duplicate on saving the RPM
        self._mock_units_rpm_collection.update.side_effect = errors.DuplicateKeyError("Uh Oh!")
        self._mock_repo_content_units_collection = mock.MagicMock(collection.Collection)
        # We need to mock the repo_content_units to have a collision
        self._mock_repo_content_units_collection.update.side_effect = errors.DuplicateKeyError("")
        self._mock_repo_content_units_collection.find.return_value = [
            {"_id": "547df04da0cfd118fc1f7069", "updated": "2014-12-02T17:01:01Z",
             "repo_id": "confused-bear", "created": "2014-12-02T17:01:01Z",
             "_ns": "repo_content_units", "unit_id": SHA_RPM['_id'],
             "unit_type_id": "rpm", "owner_type": "importer", "id": "547df04da0cfd118fc1f7069",
             "owner_id": "yum_importer"}]

        migration._migrate_rpmlike_units('rpm')

        # get_collection() should have been called three times, once for each of repos,
        # repo_content_units, and units_rpm.
        self.assertEqual(get_collection.call_count, 3)
        self.assertEqual(set([c[1] for c in get_collection.mock_calls]),
                         set([('repos',), ('repo_content_units',), ('units_rpm',)]))
        # Since the RPM's checksumtype was sha, we should have seen a call to update it to sha1.
        self._mock_units_rpm_collection.update.assert_called_once_with(
            {'_id': SHA_RPM['_id']}, {'$set': {'checksumtype': 'sha1'}})
        # Since there was a conflict in the above update call, the migration should have attempted
        # to switch all instances of the unit found in the repo_content_units collection to
        # reference its duplicate instead.
        self._mock_units_rpm_collection.find_one.assert_called_once_with(
            {'name': SHA_RPM['name'], 'epoch': SHA_RPM['epoch'], 'version': SHA_RPM['version'],
             'release': SHA_RPM['release'], 'arch': SHA_RPM['arch'],
             'checksum': SHA_RPM['checksum'], 'checksumtype': 'sha1'})
        self._mock_repo_content_units_collection.find.assert_called_once_with(
            {'unit_type_id': 'rpm', 'unit_id': SHA_RPM['_id']})
        self._mock_repo_content_units_collection.update.assert_called_once_with(
            {'_id': '547df04da0cfd118fc1f7069'}, {'$set': {'unit_id': SHA1_RPM['_id']}})
        # Since the RCU update also caused a duplicate exception, the migration should have made a
        # call to delete the RCU, and a call to decrement the content unit counts on the repo.
        self._mock_repo_content_units_collection.remove.assert_called_once_with(
            {'_id': '547df04da0cfd118fc1f7069'})
        self._mock_repos_collection.update.assert_called_once_with(
            {'id': 'confused-bear'}, {'$inc': {'content_unit_counts.rpm': -1}})
        # Lastly, the sha unit should have been removed
        self._mock_units_rpm_collection.remove.assert_called_once_with({'_id': SHA_RPM['_id']})

    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_duplicate_rpm_no_duplicate_rcu(self, get_collection):
        """
        Test for the case when there is a duplicate RPM, but there is not a duplicate in the
        repo_content_units collection.
        """
        get_collection.side_effect = self._generate_get_collection_mock()
        self._mock_units_rpm_collection = mock.MagicMock(collection.Collection)
        self._mock_units_rpm_collection.find.return_value = [SHA_RPM, SHA1_RPM]
        self._mock_units_rpm_collection.find_one.return_value = SHA1_RPM
        # This will cause a duplicate on saving the RPM
        self._mock_units_rpm_collection.update.side_effect = errors.DuplicateKeyError("Uh Oh!")
        self._mock_repo_content_units_collection = mock.MagicMock(collection.Collection)
        # This will show us as having an RCU to update
        self._mock_repo_content_units_collection.find.return_value = [
            {"_id": "547df04da0cfd118fc1f7069", "updated": "2014-12-02T17:01:01Z",
             "repo_id": "confused-bear", "created": "2014-12-02T17:01:01Z",
             "_ns": "repo_content_units", "unit_id": SHA_RPM['_id'],
             "unit_type_id": "rpm", "owner_type": "importer", "id": "547df04da0cfd118fc1f7069",
             "owner_id": "yum_importer"}]

        migration._migrate_rpmlike_units('rpm')

        # get_collection() should have been called three times, once for each of repos,
        # repo_content_units, and units_rpm.
        self.assertEqual(get_collection.call_count, 3)
        self.assertEqual(set([c[1] for c in get_collection.mock_calls]),
                         set([('repos',), ('repo_content_units',), ('units_rpm',)]))
        # Since the RPM's checksumtype was sha, we should have seen a call to update it to sha1.
        self._mock_units_rpm_collection.update.assert_called_once_with(
            {'_id': SHA_RPM['_id']}, {'$set': {'checksumtype': 'sha1'}})
        # Since there was a conflict in the above update call, the migration should have attempted
        # to switch all instances of the unit found in the repo_content_units collection to
        # reference its duplicate instead.
        self._mock_units_rpm_collection.find_one.assert_called_once_with(
            {'name': SHA_RPM['name'], 'epoch': SHA_RPM['epoch'], 'version': SHA_RPM['version'],
             'release': SHA_RPM['release'], 'arch': SHA_RPM['arch'],
             'checksum': SHA_RPM['checksum'], 'checksumtype': 'sha1'})
        self._mock_repo_content_units_collection.find.assert_called_once_with(
            {'unit_type_id': 'rpm', 'unit_id': SHA_RPM['_id']})
        self._mock_repo_content_units_collection.update.assert_called_once_with(
            {'_id': '547df04da0cfd118fc1f7069'}, {'$set': {'unit_id': SHA1_RPM['_id']}})
        # Since the RCU update was successful, we should not see any calls to decrement units or
        # remove RCUs
        self.assertEqual(self._mock_repo_content_units_collection.remove.call_count, 0)
        self.assertEqual(self._mock_repos_collection.update.call_count, 0)
        # Lastly, the sha unit should have been removed
        self._mock_units_rpm_collection.remove.assert_called_once_with({'_id': SHA_RPM['_id']})

    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_duplicate_rpm_no_rcu(self, get_collection):
        """
        Test for the case when there is a duplicate RPM, but the Unit isn't in the
        repo_content_units collection.
        """
        get_collection.side_effect = self._generate_get_collection_mock()
        self._mock_units_rpm_collection = mock.MagicMock(collection.Collection)
        self._mock_units_rpm_collection.find.return_value = [SHA_RPM, SHA1_RPM]
        self._mock_units_rpm_collection.find_one.return_value = SHA1_RPM
        # This will cause a duplicate on saving the RPM
        self._mock_units_rpm_collection.update.side_effect = errors.DuplicateKeyError("Uh Oh!")
        self._mock_repo_content_units_collection = mock.MagicMock(collection.Collection)
        # This will show us as having no RCUs to update
        self._mock_repo_content_units_collection.find.return_value = []

        migration._migrate_rpmlike_units('rpm')

        # get_collection() should have been called three times, once for each of repos,
        # repo_content_units, and units_rpm.
        self.assertEqual(get_collection.call_count, 3)
        self.assertEqual(set([c[1] for c in get_collection.mock_calls]),
                         set([('repos',), ('repo_content_units',), ('units_rpm',)]))
        # Since the RPM's checksumtype was sha, we should have seen a call to update it to sha1.
        self._mock_units_rpm_collection.update.assert_called_once_with(
            {'_id': SHA_RPM['_id']}, {'$set': {'checksumtype': 'sha1'}})
        # Since there was a conflict in the above update call, the migration should have attempted
        # to switch all instances of the unit found in the repo_content_units collection to
        # reference its duplicate instead.
        self._mock_units_rpm_collection.find_one.assert_called_once_with(
            {'name': SHA_RPM['name'], 'epoch': SHA_RPM['epoch'], 'version': SHA_RPM['version'],
             'release': SHA_RPM['release'], 'arch': SHA_RPM['arch'],
             'checksum': SHA_RPM['checksum'], 'checksumtype': 'sha1'})
        self._mock_repo_content_units_collection.find.assert_called_once_with(
            {'unit_type_id': 'rpm', 'unit_id': SHA_RPM['_id']})
        # Since the find() call returned no RCUs, there should be no calls these methods.
        self.assertEqual(self._mock_repo_content_units_collection.update.call_count, 0)
        self.assertEqual(self._mock_repo_content_units_collection.remove.call_count, 0)
        self.assertEqual(self._mock_repos_collection.update.call_count, 0)
        # Lastly, the sha unit should have been removed
        self._mock_units_rpm_collection.remove.assert_called_once_with({'_id': SHA_RPM['_id']})

    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_no_duplicates(self, get_collection):
        """
        Assert correct behavior when changing the checksum type does not cause any duplicates.
        """
        get_collection.side_effect = self._generate_get_collection_mock()
        self._mock_units_rpm_collection = mock.MagicMock(collection.Collection)
        self._mock_units_rpm_collection.find.return_value = [SHA_RPM]

        migration._migrate_rpmlike_units('rpm')

        # get_collection() should have been called three times, once for each of repos,
        # repo_content_units, and units_rpm.
        self.assertEqual(get_collection.call_count, 3)
        self.assertEqual(set([c[1] for c in get_collection.mock_calls]),
                         set([('repos',), ('repo_content_units',), ('units_rpm',)]))
        # Since the RPM's checksumtype was sha, we should have seen a call to update it to
        # sha1.
        self._mock_units_rpm_collection.update.assert_called_once_with(
            {'_id': SHA_RPM['_id']}, {'$set': {'checksumtype': 'sha1'}})
        # Since we were able to update the checksum type successfully, no calls should have been
        # made to any of the following methods
        self.assertEqual(self._mock_units_rpm_collection.find_one.call_count, 0)
        self.assertEqual(self._mock_repo_content_units_collection.find.call_count, 0)
        self.assertEqual(self._mock_repo_content_units_collection.update.call_count, 0)
        self.assertEqual(self._mock_repo_content_units_collection.remove.call_count, 0)
        self.assertEqual(self._mock_repos_collection.update.call_count, 0)
        self.assertEqual(self._mock_units_rpm_collection.remove.call_count, 0)

    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_nothing_to_do(self, get_collection):
        """
        Assert correct behavior when there are no changes to make.
        """
        get_collection.side_effect = self._generate_get_collection_mock()
        self._mock_units_rpm_collection = mock.MagicMock(collection.Collection)
        self._mock_units_rpm_collection.find.return_value = [SHA1_RPM]

        migration._migrate_rpmlike_units('rpm')

        # get_collection() should have been called three times, once for each of repos,
        # repo_content_units, and units_rpm.
        self.assertEqual(get_collection.call_count, 3)
        self.assertEqual(set([c[1] for c in get_collection.mock_calls]),
                         set([('repos',), ('repo_content_units',), ('units_rpm',)]))
        # Since the RPM's checksumtype was already sha1, we should see no update calls.
        self.assertEqual(self._mock_units_rpm_collection.update.call_count, 0)
        # Since we didn't need to update the checksum type, no calls should have been
        # made to any of the following methods
        self.assertEqual(self._mock_units_rpm_collection.find_one.call_count, 0)
        self.assertEqual(self._mock_repo_content_units_collection.find.call_count, 0)
        self.assertEqual(self._mock_repo_content_units_collection.update.call_count, 0)
        self.assertEqual(self._mock_repo_content_units_collection.remove.call_count, 0)
        self.assertEqual(self._mock_repos_collection.update.call_count, 0)
        self.assertEqual(self._mock_units_rpm_collection.remove.call_count, 0)


class TestMigrateYumMetadataFiles(unittest.TestCase):
    """
    This class contains tests for _migrate_yum_metadata_files().
    """
    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_no_change_necessary(self, get_collection):
        """
        Test for the case where no changes are necessary.
        """
        units = mock.MagicMock(spec=collection.Collection)
        units.find.return_value = SHA1_YUM_METADATA_FILE
        get_collection.return_value = units

        migration._migrate_yum_metadata_files()

        get_collection.assert_called_once_with('units_yum_repo_metadata_file')
        # Since the sum type was "sha1" already, no calls to update should have been made
        self.assertEqual(units.update.call_count, 0)

    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_update_captitalized(self, get_collection):
        """
        Test for the case where an update is necessary due to the checksum type being capitalized.
        """
        units = mock.MagicMock(spec=collection.Collection)
        units.find.return_value = CAPITALIZED_YUM_METADATA_FILE
        get_collection.return_value = units

        migration._migrate_yum_metadata_files()

        get_collection.assert_called_once_with('units_yum_repo_metadata_file')
        # The unit should have been updated to sha256 since it was SHA256
        units.update.assert_called_once_with({'_id': '912e27dd-2bff-489f-9b81-9c5425554d65'},
                                             {'$set': {'checksum_type': 'sha256'}})

    @mock.patch('pulp_rpm.plugins.migrations.0017_merge_sha_sha1.connection.get_collection',
                autospec=True)
    def test_update_sha(self, get_collection):
        """
        Test for the case where an update is necessary due to the use of "sha".
        """
        units = mock.MagicMock(spec=collection.Collection)
        units.find.return_value = SHA_YUM_METADATA_FILE
        get_collection.return_value = units

        migration._migrate_yum_metadata_files()

        get_collection.assert_called_once_with('units_yum_repo_metadata_file')
        # The unit should have been updated to sha1 since it was sha
        units.update.assert_called_once_with({'_id': '912e27dd-2bff-489f-9b81-9c5425554d65'},
                                             {'$set': {'checksum_type': 'sha1'}})
