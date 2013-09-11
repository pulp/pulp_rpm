# Copyright (c) 2010 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0


%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}


# ---- Pulp (rpm) --------------------------------------------------------------

Name: pulp-rpm
Version: 2.3.0
Release: 0.9.alpha%{?dist}
Summary: Support for RPM content in the Pulp platform
Group: Development/Languages
License: GPLv2
URL: https://fedorahosted.org/pulp/
Source0: https://fedorahosted.org/releases/p/u/%{name}/%{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch
BuildRequires:  python2-devel
BuildRequires:  python-setuptools
BuildRequires:  python-nose
BuildRequires:  rpm-python

%if 0%{?rhel} == 5
# RHEL-5
Requires: mkisofs
%else
# RHEL-6 & Fedora
Requires: genisoimage
%endif

%description
Provides a collection of platform plugins, client extensions and agent
handlers that provide RPM support.

%prep
%setup -q

%build

# Yum Distributor, ISO Plugins, Export Distributor
pushd pulp_rpm/src
%{__python} setup.py build
popd

# Yum Importer
pushd plugins
%{__python} setup.py build
popd

%install
rm -rf %{buildroot}

# Yum Distributor, ISO Plugins, Export Distributor
pushd pulp_rpm/src
%{__python} setup.py install -O1 --skip-build --root %{buildroot}
popd

pushd plugins
%{__python} setup.py install -O1 --skip-build --root %{buildroot}
popd

# Directories
mkdir -p /srv
mkdir -p %{buildroot}/%{_sysconfdir}/pulp
mkdir -p %{buildroot}/%{_sysconfdir}/pki/pulp/content
mkdir -p %{buildroot}/%{_sysconfdir}/yum.repos.d
mkdir -p %{buildroot}/%{_usr}/lib
mkdir -p %{buildroot}/%{_usr}/lib/pulp/plugins
mkdir -p %{buildroot}/%{_usr}/lib/pulp/admin/extensions
mkdir -p %{buildroot}/%{_usr}/lib/pulp/consumer/extensions
mkdir -p %{buildroot}/%{_usr}/lib/pulp/agent/handlers
mkdir -p %{buildroot}/%{_var}/lib/pulp/published/http
mkdir -p %{buildroot}/%{_var}/lib/pulp/published/https
mkdir -p %{buildroot}/%{_usr}/lib/yum-plugins/
mkdir -p %{buildroot}/%{_var}/www

# Configuration
cp -R pulp_rpm/etc/httpd %{buildroot}/%{_sysconfdir}
cp -R pulp_rpm/etc/pulp %{buildroot}/%{_sysconfdir}
cp -R pulp_rpm/etc/yum %{buildroot}/%{_sysconfdir}

# WSGI
cp -R pulp_rpm/srv %{buildroot}

# WWW
ln -s %{_var}/lib/pulp/published %{buildroot}/%{_var}/www/pub

# Extensions
cp -R pulp_rpm/extensions/admin/* %{buildroot}/%{_usr}/lib/pulp/admin/extensions
cp -R pulp_rpm/extensions/consumer/* %{buildroot}/%{_usr}/lib/pulp/consumer/extensions

# Agent Handlers
cp pulp_rpm/handlers/* %{buildroot}/%{_usr}/lib/pulp/agent/handlers

# Plugins
cp -R pulp_rpm/plugins/* %{buildroot}/%{_usr}/lib/pulp/plugins

# Yum Plugins
cp -R pulp_rpm/usr/lib/yum-plugins %{buildroot}/%{_usr}/lib

# Ghost repository file for consumers
touch %{buildroot}/%{_sysconfdir}/yum.repos.d/pulp.repo

%clean
rm -rf %{buildroot}


# define required pulp platform version.
%global pulp_version %{version}


# ---- RPM Common --------------------------------------------------------------

%package -n python-pulp-rpm-common
Summary: Pulp RPM support common library
Group: Development/Languages
Requires: python-pulp-common = %{pulp_version}

%description -n python-pulp-rpm-common
A collection of modules shared among all RPM components.

%files -n python-pulp-rpm-common
%defattr(-,root,root,-)
%dir %{python_sitelib}/pulp_rpm
%{python_sitelib}/pulp_rpm/__init__.py*
%{python_sitelib}/pulp_rpm/common/
%doc


# ---- RPM Extension Common ----------------------------------------------------

%package -n python-pulp-rpm-extension
Summary: The RPM extension common library
Group: Development/Languages
Requires: python-pulp-rpm-common = %{pulp_version}
Requires: rpm-python

%description -n python-pulp-rpm-extension
A collection of components shared among RPM extensions.

%files -n python-pulp-rpm-extension
%defattr(-,root,root,-)
%{python_sitelib}/pulp_rpm/extension/
%doc


# ---- Plugins -----------------------------------------------------------------

%package plugins
Summary: Pulp RPM plugins
Group: Development/Languages
Requires: python-pulp-rpm-common = %{pulp_version}
Requires: pulp-server = %{pulp_version}
Requires: createrepo >= 0.9.9-21
Requires: python-rhsm >= 1.8.0
Requires: grinder >= 0.1.16
Requires: pyliblzma
Requires: python-nectar >= 1.1.0
%description plugins
Provides a collection of platform plugins that extend the Pulp platform
to provide RPM specific support.

%files plugins
%defattr(-,root,root,-)
%{python_sitelib}/pulp_rpm/migrations/
%{python_sitelib}/pulp_rpm/repo_auth/
%{python_sitelib}/pulp_rpm/yum_plugin/
%{python_sitelib}/pulp_rpm/plugins/
%{python_sitelib}/*.egg-info
%config(noreplace) %{_sysconfdir}/pulp/repo_auth.conf
%config(noreplace) %{_sysconfdir}/httpd/conf.d/pulp_rpm.conf
%{_usr}/lib/pulp/plugins/types/rpm_support.json
%{_usr}/lib/pulp/plugins/types/iso_support.json
%{_usr}/lib/pulp/plugins/distributors/yum_distributor/
%{_usr}/lib/pulp/plugins/distributors/iso_distributor/
%{_sysconfdir}/pulp/vhosts80/rpm.conf
%defattr(-,apache,apache,-)
%{_var}/www/pub
%{_var}/lib/pulp/published/
%{_sysconfdir}/pki/pulp/content/
/srv/pulp/repo_auth.wsgi
%doc


# ---- Admin Extensions --------------------------------------------------------

%package admin-extensions
Summary: The RPM admin client extensions
Group: Development/Languages
Requires: python-pulp-rpm-extension = %{pulp_version}
Requires: pulp-admin-client = %{pulp_version}

%description admin-extensions
A collection of extensions that supplement and override generic admin
client capabilites with RPM specific features.

%files admin-extensions
%defattr(-,root,root,-)
%{_usr}/lib/pulp/admin/extensions/rpm_admin_consumer/
%{_usr}/lib/pulp/admin/extensions/rpm_repo/
%{_usr}/lib/pulp/admin/extensions/iso/
%doc


# ---- Consumer Extensions -----------------------------------------------------

%package consumer-extensions
Summary: The RPM consumer client extensions
Group: Development/Languages
Requires: python-pulp-rpm-extension = %{pulp_version}
Requires: pulp-consumer-client = %{pulp_version}

%description consumer-extensions
A collection of extensions that supplement and override generic consumer
client capabilites with RPM specific features.

%files consumer-extensions
%defattr(-,root,root,-)
%{_usr}/lib/pulp/consumer/extensions/rpm_consumer/
%doc


# ---- Agent Handlers ----------------------------------------------------------

%package handlers
Summary: Pulp agent rpm handlers
Group: Development/Languages
Requires: python-rhsm
Requires: python-pulp-rpm-common = %{pulp_version}
Requires: python-pulp-agent-lib = %{pulp_version}

%description handlers
A collection of handlers that provide both Linux and RPM specific
functionality within the Pulp agent.  This includes RPM install, update,
uninstall; RPM profile reporting; binding through yum repository
management and Linux specific commands such as system reboot.

%files handlers
%defattr(-,root,root,-)
%{python_sitelib}/pulp_rpm/handler/
%{_sysconfdir}/pulp/agent/conf.d/bind.conf
%{_sysconfdir}/pulp/agent/conf.d/linux.conf
%{_sysconfdir}/pulp/agent/conf.d/rpm.conf
%ghost %{_sysconfdir}/yum.repos.d/pulp.repo
%{_usr}/lib/pulp/agent/handlers/bind.py*
%{_usr}/lib/pulp/agent/handlers/linux.py*
%{_usr}/lib/pulp/agent/handlers/rpm.py*
%doc


# ---- YUM Plugins -------------------------------------------------------------

%package yumplugins
Summary: Yum plugins supplementing in Pulp consumer operations
Group: Development/Languages
Requires: yum
Requires: python-rhsm >= 1.8.0
Requires: python-pulp-bindings = %{pulp_version}

%description yumplugins
A collection of yum plugins supplementing Pulp consumer operations.

%files yumplugins
%defattr(-,root,root,-)
%{_sysconfdir}/yum/pluginconf.d/pulp-profile-update.conf
%{_usr}/lib/yum-plugins/pulp-profile-update.py*
%doc



%changelog
* Tue Sep 10 2013 Jeff Ortel <jortel@redhat.com> 2.3.0-0.9.alpha
- 997177 - Move uploads to the content directory instead of copying them
  (bcourt@redhat.com)
- 976845 - updating descriptions for iso repo sync and publish commands as both
  don't support status sub-command (skarmark@redhat.com)

* Fri Sep 06 2013 Barnaby Court <bcourt@redhat.com> 2.3.0-0.8.alpha
- 1004897 - Fix bug where distributor validate_config is finding relative path
  conflicts with the repository that is being updated (bcourt@redhat.com)
- 979587 - updating consumer update command to default to all packages instead
  of accepting -a flag. (skarmark@redhat.com)
- 979587 - updating consumer update command to default to all packages instead
  of accepting -a flag (skarmark@redhat.com)
- 1004086 - Rename migration #11 to #7, and increment migration version #7 to
  #10 by one. (rbarlow@redhat.com)
- 1004049 - added a migration for errata that have the old "from_str" key
  (mhrivnak@redhat.com)
- 915330 - Fix performance degradation of importer and distributor
  configuration validation as the number of repositories increased
  (bcourt@redhat.com)

* Fri Aug 30 2013 Barnaby Court <bcourt@redhat.com> 2.3.0-0.7.alpha
- Pulp rebuild

* Thu Aug 29 2013 Jeff Ortel <jortel@redhat.com> 2.3.0-0.6.alpha
- Pulp rebuild

* Thu Aug 29 2013 Barnaby Court <bcourt@redhat.com> 2.3.0-0.5.alpha
- Pulp rebuild

* Tue Aug 27 2013 Jeff Ortel <jortel@redhat.com> 2.3.0-0.4.alpha
- Pulp rebuild

* Tue Aug 27 2013 Jeff Ortel <jortel@redhat.com> 2.3.0-0.3.alpha
- 956711 - Raise an error to the client if an attempt is made to install an
  errata that does not exist in a repository bound to the consumer
  (bcourt@redhat.com)
- 999516 - Block plugin tests from running on RHEL 5 (bcourt@redhat.com)
- 999516 - Block plugin tests from running on RHEL 5 (bcourt@redhat.com)
- 999516 - Block plugin tests from running on RHEL 5 (bcourt@redhat.com)
- 999516 - Block plugin tests from running on RHEL 5 (bcourt@redhat.com)
- 991500 - changes with respect to updated get_repo_units conduit call to
  return plugin units instead of dictionary (skarmark@redhat.com)
- 996625 - sync now always saves groups and categories, in case their metadata
  has changed. (mhrivnak@redhat.com)
- 981782 - Add the ability to change the skip options on the rpm repo update
  command (bcourt@redhat.com)
- 995572 - fixed a treeinfo file parsing error when dealing with treeinfo files
  that do not include a "variant" value. (mhrivnak@redhat.com)
- 995096 - fixed multiple bugs in errata parsing and added a test
  (mhrivnak@redhat.com)
- 995146 - Rename one of two migrations that were sharing version 0012.
  (rbarlow@redhat.com)
- 993452 - when uploading an RPM, the "location" tag in its generated repodata
  XML is now correct. (mhrivnak@redhat.com)
- 980181 - added listing file generation on publish and unpublish
  (jason.connor@gmail.com)

* Thu Aug 01 2013 Jeff Ortel <jortel@redhat.com> 2.3.0-0.2.alpha
- 988919 - non-standard repo metadata files that happen to be sqlite files can
  now be downloaded successfully during a sync (mhrivnak@redhat.com)
- 988005 - uploads of units that are not RPMs work again (mhrivnak@redhat.com)
- 986026 - Added a migration to upgrade conditional_package_names from v1 to
  v2. (rbarlow@redhat.com)
- 987663 - syncing of a distribution now uses a nectar factory to get the most
  appropriate downloader type for a given URL, defaulting to the requests
  library for HTTP. It also now uses the nectar config options that are
  specified in the importer config instead of always using a default config.
  (mhrivnak@redhat.com)
- 952386 - Cleanup published files when ISODistributors are removed.
  (rbarlow@redhat.com)
- 976579 - adding creation of Packages symlink to contents
  (jason.connor@gmail.com)
- 975543 - Change the ISO "content" command name to "isos".
  (rbarlow@redhat.com)
- 974590 - Handle multiple calls to copy metadata files.
  (jason.dobies@redhat.com)
- 950772 - Don't attempt state transitions away from STATE_CANCELLED.
  (rbarlow@redhat.com)

* Mon Jul 15 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.21.beta
- 984104 - fixed a bug that caused multiple calls to group copy with the
  --recursive option to fail (mhrivnak@redhat.com)
- 983323 - fixed an XML parsing incompatibility with python 2.6 where the
  default XML namespace was being mishandled. (mhrivnak@redhat.com)

* Tue Jul 09 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.20.beta
- 982649 - fixing a python 2.6 incompatibility which caused writing of XML for
  individual packages to fail. (mhrivnak@redhat.com)

* Mon Jul 08 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.19.beta
- Pulp rebuild

* Wed Jul 03 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.18.beta
- Pulp rebuild

* Wed Jul 03 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.17.beta
- 976042 - source RPMs are now categorized correctly as type "srpm".
  (mhrivnak@redhat.com)
- 980572 - can now import groups from comps.xml files where some groups entries
  don't include a "uservisible" value, such as in a Fedora 18 repo.
  (mhrivnak@redhat.com)
- 973402 - fixed a mishandling of XML namespaces in repo metadata that led to
  problems when installing packages with dependencies from a published repo.
  (mhrivnak@redhat.com)

* Thu Jun 20 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.5.beta
- 976333 - Fixed importer config look up to use constant
  (jason.dobies@redhat.com)
- 976333 - Updated the relative URL calculation to use the new key for feed
  (jason.dobies@redhat.com)

* Mon Jun 17 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.4.beta
- 974663 - the importer can now save repo metadata files of unknown types in
  the database as units (mhrivnak@redhat.com)
- 972909 - Extract the provides/requires fields from the XML server-side.
  (jason.dobies@redhat.com)
- 973387 - fix fsize attribute error on unit install progress reporting.
  (jortel@redhat.com)
- 972909 - invalid requires and provides data originally generated by the v2.1
  upload workflow now gets corrected by a migration. (mhrivnak@redhat.com)

* Tue Jun 11 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.3.beta
- 972911 - migration 0010 now works. Had to account for cases where a
  provide/require had already been converted, and cases where encoding was non-
  ASCII. (mhrivnak@redhat.com)
- 962941 - Don't use ISO names as keys in the progress report.
  (rbarlow@redhat.com)
- 971953 - Work around to limit RAM usage during RPM removal
  (jason.dobies@redhat.com)
- 970795 - Make sure the publishing build directory is empty before publishing
  ISOs. (rbarlow@redhat.com)
- 971161 - Added distribution failed state rendering that was removed since 2.1
  (jason.dobies@redhat.com)
- 955700 - Merge commit 'ba158afb1960799fb8f0dd458f5da21dfe936507' into pulp
  (skarmark@redhat.com)
- 971200 - Fixed pagination of iterables so that a non-generator doesn't cause
  an infinite loop. (mhrivnak@redhat.com)
- 969529 - Remove the content-unit option in addition to the type option
  (jason.dobies@redhat.com)
- 971154 - Add an uploads section with appropriate commands to the ISO CLI.
  (rbarlow@redhat.com)
- 971167 - during repo sync, before each RPM's XML snippet from primary.xml
  gets saved to the database, the <location/> tag is modified so that the href
  attribute contains only the file name, and no other leading path or URL
  elements. This matches the expectation that files are published at the root
  of the repository. (mhrivnak@redhat.com)
- 971157 - the new yum importer can now at sync time skip the four types
  mentioned in the --skip option of the pulp-admin rpm repo create command.
  Those types are rpm, drpm, erratum, and distribution. (mhrivnak@redhat.com)
- 971060 - fixing copy of distributions. Also had to fix the text output of a
  successful command, which was incorrectly displaying the distribution
  identity. (mhrivnak@redhat.com)
- 970777 - the new importer no longer looks for the non-existant CLI option
  --copy-children during a copy operation. (mhrivnak@redhat.com)
- 923334 - fix processing of task.result and restructure command to work with a
  list of tasks. (jortel@redhat.com)
- 955700 - Added all command to pulp-admin rpm repo copy to copy all content
  units and unit tests for the same (skarmark@redhat.com)

* Thu Jun 06 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.2.beta
- 969579 - Further corrections to the deps for yumplugins
  (jason.dobies@redhat.com)
- 969579 - The client-side yum plugins don't require the server
  (jason.dobies@redhat.com)
- 971138 - Include a missing module from my last commit. (rbarlow@redhat.com)
- 971138 - Add a new contents command to the CLI for ISO repos.
  (rbarlow@redhat.com)
- 970741 - Updated nectar depedency for error_msg support
  (jason.dobies@redhat.com)
- 970787 - Add a unit removal command to the ISO client. (rbarlow@redhat.com)
- 970746 - Updated recipes for new proxy_* config names
  (jason.dobies@redhat.com)
- 970636 - Scope the fields loaded for the copy to minimize RAM.
  (jason.dobies@redhat.com)
- 970269 - making the 'id' attribute of errata references optional, since
  evidence suggests that they are not present in rhel6 repos.
  (mhrivnak@redhat.com)
- 970267 - removing the use of a parameter that didn't exist in python 2.6.
  Thankfully I was passing the default value anyway, so the 2.6 behavior is
  what I want even without the parameter. (mhrivnak@redhat.com)

* Tue Jun 04 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.1.beta
- 968535 - leverage --no-compress; need to compensate for anaconda bug related
  to compressed metadata. (jortel@redhat.com)
- 968543 - remove conditional in pulp_version macro. (jortel@redhat.com)
- 963774 - Added the *sort_index fields to the search indexes
  (jason.dobies@redhat.com)
- 965818 - Added translation from new format for provides/requires to a more
  user-friendly output (jason.dobies@redhat.com)
- 955702 - updating documentation for mirroring a repository with a valid url
  and corresponding output (skarmark@redhat.com)
- 966178 - Added default to remove-missing (jason.dobies@redhat.com)

* Thu May 30 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.15.alpha
- 950690 - Removed copy commands that aren't supported in the plugin
  (jason.dobies@redhat.com)

* Fri May 24 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.14.alpha
- 966178 - Added default to remove-missing (jason.dobies@redhat.com)

* Thu May 23 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.13.alpha
- Pulp rebuild

* Thu May 23 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.12.alpha
- Pulp rebuild

* Tue May 21 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.11.alpha
- Pulp rebuild

* Mon May 20 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.10.alpha
- Pulp rebuild

* Mon May 20 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.9.alpha
- Pulp rebuild

* Fri May 17 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.8.alpha
- Pulp rebuild

* Mon May 13 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.5.alpha
- Pulp rebuild

* Mon May 13 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.3.alpha
- 959823 - splitting up a query for existing units by type, allowing each query
  to limit which fields are loaded, thus reducing the memory footprint.
  (mhrivnak@redhat.com)
- 957870 - translate errata into full NEVRA package names. (jortel@redhat.com)
- 956372 - fix errata installs. (jortel@redhat.com)
- 954038 - minor changes to fix unit tests (skarmark@redhat.com)
- 954038 - minor changes to fix unit tests (skarmark@redhat.com)
- 954038 - minor renaming (skarmark@redhat.com)
- 954038 - updating rpm package profiler applicability api to accept unit ids
  instead of unit keys (skarmark@redhat.com)
- 954038 - updating errata profiler applicability api for accept unit ids
  instead of unit keys (skarmark@redhat.com)
- 887000 - leveraging new cancel report to keep cancelled state
  (jason.connor@gmail.com)
- 924778 - Provide option to skip re-uploading existing files
  (jason.dobies@redhat.com)
- 953575 - Corrected relative_url to being a required parameter
  (jason.dobies@redhat.com)
- 950695 - Mike's going to take the presto data out of the scratch pad
  entirely, so even if this test wasn't horribly broken by making a live
  connection, it wouldn't be valid in another month anyway.
  (jason.dobies@redhat.com)
- 955172 - Removing rhsm from our repo and now using the regular python-rhsm
  (mhrivnak@redhat.com)

* Fri Apr 19 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.2.alpha
- 953665 - added the ability for copy operations to not also copy child units,
  such as a group copying its RPMs. Also restricted the fetching of existing
  units to their unit key fields, which reduced RAM use tremendously. Copying a
  RHEL6 repo went from using about 4.3GB of RAM to < 100MB.
  (mhrivnak@redhat.com)
- 928084 - The ISOImporter now handles malformed PULP_MANIFEST files.
  (rbarlow@redhat.com)

* Fri Apr 12 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-0.1.alpha
- 950740 - add support {?dist} in the Release: in .spec files.
  (jortel@redhat.com)
- 947927 - When looking for nested elements in a copy, only check the source
  repository, not all of Pulp. By nested elements I mean RPMs in a package
  group or groups in a package category. (jason.dobies@redhat.com)
- 928509 - Added errata v. consumer centric applicability reports
  (jason.dobies@redhat.com)
- 949008 - Use a value of 2 for pycurl's SSL_VERIFYHOST setting instead of 1.
  (rbarlow@redhat.com)
- 949004 - Append trailing slashes to ISO feed URLs when they lack them.
  (rbarlow@redhat.com)
- 873313 - Very high memory usage during repo sync (jwmatthews@gmail.com)
- 923448 - made the changelog and filelist metadata migration more robust in
  terms of handling non-utf8 text encoding (mhrivnak@redhat.com)
- 923351 - updating errata profiler applicability function to add errata
  details to the applicability report (skarmark@redhat.com)
- 923794 - The error report coming out of the yum importer can't be serialized
  to the database (jwmatthews@gmail.com)
- 923792 - Errata queries during sync don't properly limit returned data
  (jwmatthews@gmail.com)
- 920322 - Use import_units() inside of _import_pkg_category_unit() to ensure
  that we handle package groups correctly. (rbarlow@redhat.com)
- 919519 - Adjust documentation to reflect new export publishing location.
  (rbarlow@redhat.com)
- 919519 - The export distributor now published to /pulp/exports instead of
  /pulp/isos. (rbarlow@redhat.com)
- 912836 - Fix disconnect between rpm repo extension and repolib with regard to
  GPG.keys. (jortel@redhat.com)
- 917083 - ghost pulp.repo so it's cleaned up on uninstall. (jortel@redhat.com)

* Mon Mar 04 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.19.alpha
- 902514 - removed the <VirtualHost *:80> block in favor of using the
  platform's authoritative one. (mhrivnak@redhat.com)
- 916336 - Change the default num_threads to 4. (rbarlow@redhat.com)
- 913172 - Fixed a section heading and added info about configuring a proxy for
  global use (mhrivnak@redhat.com)
- 889565 - Corrected configuration options from being flags to options
  (jason.dobies@redhat.com)

* Tue Feb 26 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.18.alpha
- Pulp rebuild

* Tue Feb 26 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.17.alpha
- Pulp rebuild

* Mon Feb 25 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.16.alpha
- Pulp rebuild

* Fri Feb 22 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.14.alpha
- 905119 - Remove unused /ks alias from the pulp_rpm.conf file.
  (rbarlow@redhat.com)

* Thu Feb 21 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.13.alpha
- Pulp rebuild

* Tue Feb 19 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.12.alpha
- Pulp rebuild

* Thu Feb 14 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.10.alpha
- Pulp rebuild

* Thu Feb 14 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.9.alpha
- Pulp rebuild

* Wed Feb 13 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.8.alpha
- Pulp rebuild

* Wed Feb 13 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.7.alpha
- Pulp rebuild

* Tue Feb 12 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.5.alpha
- Pulp rebuild

* Tue Feb 12 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.4.alpha
- 700945 - Include changelog and filelist info as part of rpm metadata
  (pkilambi@redhat.com)

* Tue Feb 05 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.3.alpha
- Pulp rebuild

* Tue Feb 05 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.2.alpha
- 782490 - include the distributor config key as part of key list
  (pkilambi@redhat.com)
- 876725 - minor update to effectively use details.get (skarmark@redhat.com)
- 782490 - pkgtags are currently ignored, skip them by default. User has a
  choice to enable it in yum_distributor config (pkilambi@redhat.com)
- 903387 - include /var/lib/pulp/published in pulp-rpm-plugins.
  (jortel@redhat.com)
- 896027 - pulp-rpm-common owns site-packages/pulp_rpm directory only.
  (jortel@redhat.com)
- 903262 - Added boolean parser to only-newest command
  (jason.dobies@redhat.com)
- 876725 - adding support for best effort install of content and unit tests
  (skarmark@redhat.com)

* Sat Jan 19 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-0.1.alpha
- 894467 - Fixed incorrect validation for proxy port (jason.dobies@redhat.com)
- 891423 - fix pkg group and category copy (pkilambi@redhat.com)
- 891731 - fix the metadata for uploaded rpms to remove relaptive paths from
  location tags (pkilambi@redhat.com)
- 891760 - Remove unnecessary and risky logging statements.
  (rbarlow@redhat.com)
- 887041 - Add troubleshooting section to docs. (rbarlow@redhat.com)
- 887032 - Added docs about how to get entitlement certificates.
  (rbarlow@redhat.com)
- 887959 - Removing NameVirtualHost entries from plugin httpd conf files and
  adding it only at one place in main pulp.conf (skarmark@redhat.com)
- 886240 - fixing distribution sync and publish * set the distro location when
  grinder is invoked so treeinfo gets downloaded and symlinked to right
  location * fix the publish to lookup treeinfo and symlink to publish location
  (pkilambi@redhat.com)
- 886240 - yum's update_md skips updated date via xml generation, adding a
  check to see if its missing and fallback to issued date instead
  (pkilambi@redhat.com)
- 887388 - Fixed issue with non --details listing (jason.dobies@redhat.com)
- 886240 - Fixes generation of updateinfo XML if an errata spans more than 1
  collection, yum will output the XML with an extra '</pkglist>' interspersed
  between each <collection>. (jmatthews@redhat.com)
- 887388 - Strip out the feed SSL info and replace with safe message
  (jason.dobies@redhat.com)
- 887368 - implement bind handler clean(). (jortel@redhat.com)
- 886240 - updated comps parsing so it will auto wrap a file with GzipFile if
  it ends with .gz, even if comes from 'groups' data and not 'group_gz'
  (jmatthews@redhat.com)
- 887123 - Process --verify-feed-ssl as a boolan. (rbarlow@redhat.com)
- 887026 - The yum distributor should not have been storing this value in
  server.conf. (jason.dobies@redhat.com)
- 886986 - Default to verifying feed SSL certificates. (rbarlow@redhat.com)
- 885264 - bump grinder requires to: 0.1.11-1. (jortel@redhat.com)
- 886240 - repo sync for a repo created with a feed of /var/lib/pulp of another
  repo results in less number of contents than the original repo
  (jmatthews@redhat.com)
- 886240 - repo sync for a repo created with a feed of /var/lib/pulp of another
  repo results in less number of contents than the original repo Updated logic
  for pagination of package metadata (jmatthews@redhat.com)
- 857528 - Added missing feed message to the progress report so the client sees
  it (jason.dobies@redhat.com)
- 885264 - require grinder 0.1.10 (jortel@redhat.com)
- 881355 - fixed errata install CLI result parsing. (jortel@redhat.com)
- 882421 - moving remove() method into the platform library so it can be used
  by other extension families (mhrivnak@redhat.com)
- 874241 - Alter the CLI help text to specify that relative_urls must match our
  regex. (rbarlow@redhat.com)
- 874241 - Allow relative URLs to have the forward slash character.
  (rbarlow@redhat.com)
- 874241 - Only allow alphanumerics, underscores, and dashes in the
  relative_url. (rbarlow@redhat.com)
- 876637 - adding validation for empty feed url (skarmark@redhat.com)
- 881932 - updated bind/unbind output. (jortel@redhat.com)
- 880441 - Ported over group commands from builtins (temporary hack for 2.0)
  (jason.dobies@redhat.com)
- 880391 - added remove distribution cli command (skarmark@redhat.com)
- 877161 - importer side of changes to orphan distribution units
  (pkilambi@redhat.com)
- 877047 - if a file already exists, do not try to create a symlink
  (pkilambi@redhat.com)
- 881639 - fix error message when binding does not exist. (jortel@redhat.com)
- 869099 - fix to the plugin progress callback so delta rpm progress doesnt
  override rpm progress (pkilambi@redhat.com)
- 866491 - Translate bad data property name into CLI flag
  (jason.dobies@redhat.com)
- 858855 - Directory created at runtime but included here so that it's cleaned
  up when rpm plugins are uninstalled. (jortel@redhat.com)
- 862290 - Added support for non-RPM repo listing (jason.dobies@redhat.com)
- 878548 - Added empty conf files for the plugins in case we need to tell users
  to edit them in the future. I'd have liked to add comments about possible
  values, but comments aren't supported in JSON. (jason.dobies@redhat.com)
- 877488 - Removing publish schedules section (jason.dobies@redhat.com)
- 873419 - searching for RPMs with the --details flag works properly again
  (mhrivnak@redhat.com)
- 876260 - Fixed the export_distributor removal fix (jason.dobies@redhat.com)
- 875163 - Remove the export distributor from being displayed in --details
  (jason.dobies@redhat.com)
- 875163 - use group as the xml filename when generating comps so modifyrepo
  uses that as type id which yum expects (pkilambi@redhat.com)

* Thu Dec 20 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.19.rc
- Pulp rebuild

* Wed Dec 19 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.19.beta
- Pulp rebuild

* Tue Dec 18 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.18.beta
- 887959 - Removing NameVirtualHost entries from plugin httpd conf files and
  adding it only at one place in main pulp.conf (skarmark@redhat.com)
- 886240 - fixing distribution sync and publish * set the distro location when
  grinder is invoked so treeinfo gets downloaded and symlinked to right
  location * fix the publish to lookup treeinfo and symlink to publish location
  (pkilambi@redhat.com)
- 886240 - yum's update_md skips updated date via xml generation, adding a
  check to see if its missing and fallback to issued date instead
  (pkilambi@redhat.com)
- 887388 - Fixed issue with non --details listing (jason.dobies@redhat.com)
- 886240 - Fixes generation of updateinfo XML if an errata spans more than 1
  collection, yum will output the XML with an extra '</pkglist>' interspersed
  between each <collection>. (jmatthews@redhat.com)
- 887388 - Strip out the feed SSL info and replace with safe message
  (jason.dobies@redhat.com)
- 887368 - implement bind handler clean(). (jortel@redhat.com)
- 886240 - updated comps parsing so it will auto wrap a file with GzipFile if
  it ends with .gz, even if comes from 'groups' data and not 'group_gz'
  (jmatthews@redhat.com)
- 887123 - Process --verify-feed-ssl as a boolan. (rbarlow@redhat.com)

* Thu Dec 13 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.17.beta
- 887026 - The yum distributor should not have been storing this value in
  server.conf. (jason.dobies@redhat.com)
- 886986 - Default to verifying feed SSL certificates. (rbarlow@redhat.com)
- 885264 - bump grinder requires to: 0.1.11-1. (jortel@redhat.com)

* Thu Dec 13 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.15.beta
- 886240 - repo sync for a repo created with a feed of /var/lib/pulp of another
  repo results in less number of contents than the original repo
  (jmatthews@redhat.com)
- 886240 - repo sync for a repo created with a feed of /var/lib/pulp of another
  repo results in less number of contents than the original repo Updated logic
  for pagination of package metadata (jmatthews@redhat.com)
- 857528 - Added missing feed message to the progress report so the client sees
  it (jason.dobies@redhat.com)

* Mon Dec 10 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.14.beta
- 885264 - require grinder 0.1.10 (jortel@redhat.com)

* Fri Dec 07 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.13.beta
- Pulp rebuild

* Thu Dec 06 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.12.beta
- 881355 - fixed errata install CLI result parsing. (jortel@redhat.com)
- 882421 - moving remove() method into the platform library so it can be used
  by other extension families (mhrivnak@redhat.com)
- 874241 - Alter the CLI help text to specify that relative_urls must match our
  regex. (rbarlow@redhat.com)
- 874241 - Allow relative URLs to have the forward slash character.
  (rbarlow@redhat.com)
- 874241 - Only allow alphanumerics, underscores, and dashes in the
  relative_url. (rbarlow@redhat.com)
- 876637 - adding validation for empty feed url (skarmark@redhat.com)
- 881932 - updated bind/unbind output. (jortel@redhat.com)
- 880441 - Ported over group commands from builtins (temporary hack for 2.0)
  (jason.dobies@redhat.com)
- 880391 - added remove distribution cli command (skarmark@redhat.com)
- 877161 - importer side of changes to orphan distribution units
  (pkilambi@redhat.com)

* Thu Nov 29 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.11.beta
- Pulp rebuild

* Thu Nov 29 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.10.beta
- 877047 - if a file already exists, do not try to create a symlink
  (pkilambi@redhat.com)
- 881639 - fix error message when binding does not exist. (jortel@redhat.com)
- 869099 - fix to the plugin progress callback so delta rpm progress doesnt
  override rpm progress (pkilambi@redhat.com)
- 866491 - Translate bad data property name into CLI flag
  (jason.dobies@redhat.com)
- 858855 - Directory created at runtime but included here so that it's cleaned
  up when rpm plugins are uninstalled. (jortel@redhat.com)
- 862290 - Added support for non-RPM repo listing (jason.dobies@redhat.com)

* Mon Nov 26 2012 Jay Dobies <jason.dobies@redhat.com> 2.0.6-0.9.beta
- Pulp rebuild

* Tue Nov 20 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.3.beta
- 878548 - Added empty conf files for the plugins in case we need to tell users
  to edit them in the future. I'd have liked to add comments about possible
  values, but comments aren't supported in JSON. (jason.dobies@redhat.com)
- 877488 - Removing publish schedules section (jason.dobies@redhat.com)
- 873419 - searching for RPMs with the --details flag works properly again
  (mhrivnak@redhat.com)
- 876260 - Fixed the export_distributor removal fix (jason.dobies@redhat.com)
- 875163 - Remove the export distributor from being displayed in --details
  (jason.dobies@redhat.com)
- 875163 - use group as the xml filename when generating comps so modifyrepo
  uses that as type id which yum expects (pkilambi@redhat.com)
- 876174 - Migrated over missing consumer commands (jason.dobies@redhat.com)

* Mon Nov 12 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.2.beta
- Pulp rebuild

* Mon Nov 12 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-0.1.beta
- Pulp rebuild
