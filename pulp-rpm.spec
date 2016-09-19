%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

%if 0%{?rhel} == 5
%define pulp_admin 0
%define pulp_server 0
%else
%define pulp_admin 1
%define pulp_server 1
%endif


# ---- Pulp (rpm) --------------------------------------------------------------

Name: pulp-rpm
Version: 2.9.3
Release: 1%{?dist}
Summary: Support for RPM content in the Pulp platform
Group: Development/Languages
License: GPLv2
URL: https://fedorahosted.org/pulp/
Source0: https://github.com/pulp/pulp_rpm/archive/%{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch
BuildRequires:  python2-devel
BuildRequires:  python-setuptools
BuildRequires:  rpm-python

%description
Provides a collection of platform plugins, client extensions and agent
handlers that provide RPM support.

%prep
%setup -q

%build

pushd common
%{__python} setup.py build
popd

%if %{pulp_admin}
pushd extensions_admin
%{__python} setup.py build
popd
%endif # End pulp_admin if block

pushd extensions_consumer
%{__python} setup.py build
popd

pushd handlers
%{__python} setup.py build
popd

%if %{pulp_server}
pushd plugins
%{__python} setup.py build
popd
%endif # End pulp_server if block

%install
rm -rf %{buildroot}

mkdir -p %{buildroot}/%{_sysconfdir}/pulp

pushd common
%{__python} setup.py install -O1 --skip-build --root %{buildroot}
popd

%if %{pulp_admin}
pushd extensions_admin
%{__python} setup.py install -O1 --skip-build --root %{buildroot}
popd

mkdir -p %{buildroot}/%{_usr}/lib/pulp/admin/extensions
%endif # End pulp_admin if block

pushd extensions_consumer
%{__python} setup.py install -O1 --skip-build --root %{buildroot}
popd

pushd handlers
%{__python} setup.py install -O1 --skip-build --root %{buildroot}
popd

%if %{pulp_server}
pushd plugins
%{__python} setup.py install -O1 --skip-build --root %{buildroot}
popd

mkdir -p %{buildroot}/%{_usr}/lib/pulp/plugins
mkdir -p %{buildroot}/%{_var}/lib/pulp/published/yum/http
mkdir -p %{buildroot}/%{_var}/lib/pulp/published/yum/https

cp -R plugins/etc/httpd %{buildroot}/%{_sysconfdir}
cp -R plugins/etc/pulp %{buildroot}/%{_sysconfdir}

# Distribution XSD files
mkdir -p %{buildroot}/%{_usr}/share/pulp-rpm
cp -R plugins/usr/share/pulp-rpm %{buildroot}/%{_usr}/share/
%endif # End pulp_server if block

# Directories
mkdir -p %{buildroot}/%{_sysconfdir}/pki/pulp/content
mkdir -p %{buildroot}/%{_sysconfdir}/yum.repos.d
mkdir -p %{buildroot}/%{_usr}/lib/pulp/consumer/extensions
mkdir -p %{buildroot}/%{_usr}/lib/pulp/agent/handlers

# Configuration
cp -R handlers/etc/yum %{buildroot}/%{_sysconfdir}
cp -R handlers/etc/pulp %{buildroot}/%{_sysconfdir}

# Yum Plugins
cp -R handlers/usr/lib/yum-plugins %{buildroot}/%{_usr}/lib

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
Obsoletes: python-pulp-rpm-extension <= 2.4.0

%description -n python-pulp-rpm-common
A collection of modules shared among all RPM components.

%files -n python-pulp-rpm-common
%defattr(-,root,root,-)
%dir %{python_sitelib}/pulp_rpm
%{python_sitelib}/pulp_rpm_common*.egg-info
%{python_sitelib}/pulp_rpm/__init__.py*
%{python_sitelib}/pulp_rpm/extensions/__init__.py*
%{python_sitelib}/pulp_rpm/common/
%doc LICENSE COPYRIGHT

# ---- Plugins -----------------------------------------------------------------
%if %{pulp_server}
%package plugins
Summary: Pulp RPM plugins
Group: Development/Languages
Requires: python-pulp-rpm-common = %{pulp_version}
Requires: python-pulp-oid_validation >= 2.7.0
Requires: pulp-server = %{pulp_version}
Requires: createrepo >= 0.9.9-21
Requires: createrepo_c >= 0.4.1-1
Requires: python-rhsm >= 1.8.0
Requires: pyliblzma
Requires: python-nectar >= 1.2.1
Requires: genisoimage
Requires: m2crypto
Requires: python-lxml
Requires: repoview

%description plugins
Provides a collection of platform plugins that extend the Pulp platform
to provide RPM specific support.

%files plugins
%defattr(-,root,root,-)
%{python_sitelib}/pulp_rpm/plugins/
%{python_sitelib}/pulp_rpm/yum_plugin/
%{python_sitelib}/pulp_rpm_plugins*.egg-info
%config(noreplace) %{_sysconfdir}/httpd/conf.d/pulp_rpm.conf
%{_usr}/share/pulp-rpm/
%{_sysconfdir}/pulp/vhosts80/rpm.conf
%defattr(-,apache,apache,-)
%{_var}/lib/pulp/published/yum/
%{_sysconfdir}/pki/pulp/content/
%doc LICENSE COPYRIGHT
%endif # End pulp_server if block


# ---- Admin Extensions --------------------------------------------------------
%if %{pulp_admin}
%package admin-extensions
Summary: The RPM admin client extensions
Group: Development/Languages
Requires: pulp-admin-client = %{pulp_version}
Requires: python-pulp-rpm-common = %{pulp_version}

%description admin-extensions
A collection of extensions that supplement and override generic admin
client capabilites with RPM specific features.

%files admin-extensions
%defattr(-,root,root,-)
%{python_sitelib}/pulp_rpm_extensions_admin*.egg-info
%{python_sitelib}/pulp_rpm/extensions/admin/
%doc LICENSE COPYRIGHT
%endif # End pulp_admin if block


# ---- Consumer Extensions -----------------------------------------------------

%package consumer-extensions
Summary: The RPM consumer client extensions
Group: Development/Languages
Requires: pulp-consumer-client = %{pulp_version}

%description consumer-extensions
A collection of extensions that supplement and override generic consumer
client capabilites with RPM specific features.

%files consumer-extensions
%defattr(-,root,root,-)
%{python_sitelib}/pulp_rpm_extensions_consumer*.egg-info
%{python_sitelib}/pulp_rpm/extensions/consumer/
%doc LICENSE COPYRIGHT


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
%{python_sitelib}/pulp_rpm_handlers*.egg-info
%{python_sitelib}/pulp_rpm/handlers/
%{_sysconfdir}/pulp/agent/conf.d/bind.conf
%{_sysconfdir}/pulp/agent/conf.d/linux.conf
%{_sysconfdir}/pulp/agent/conf.d/rpm.conf
%ghost %{_sysconfdir}/yum.repos.d/pulp.repo
%doc LICENSE COPYRIGHT


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
%doc LICENSE COPYRIGHT



%changelog
* Tue Sep 13 2016 Sean Myers <sean.myers@redhat.com> 2.9.3-0.2.beta
- Pulp rebuild

* Tue Aug 30 2016 Sean Myers <sean.myers@redhat.com> 2.9.3-0.1.beta
- Pulp rebuild

* Thu Aug 04 2016 Sean Myers <sean.myers@redhat.com> 2.9.2-0.1.beta
- Pulp rebuild

* Tue Jul 19 2016 Sean Myers <sean.myers@redhat.com> 2.9.1-0.1.beta
- Pulp rebuild

* Thu Jun 30 2016 Sean Myers <sean.myers@redhat.com> 2.9.0-0.3.beta
- Pulp rebuild

* Tue Jun 21 2016 Sean Myers <sean.myers@redhat.com> 2.9.0-0.2.beta
- Pulp rebuild

* Wed Jun 15 2016 Sean Myers <sean.myers@redhat.com> 2.9.0-0.1.beta
- 1876 - Add in a sample program to generate the file (bkearney@redhat.com)
- fixed sync for reference title (jluza@redhat.com)
- 1782 - reboot_suggested is False by default if during unit upload there was
  not specified any value. (ipanova@redhat.com)

* Wed Apr 06 2016 Sean Myers <sean.myers@redhat.com> 2.8.2-1
- Pulp rebuild

* Tue Apr 05 2016 Sean Myers <sean.myers@redhat.com> 2.8.1-1
- Pulp rebuild

* Wed Mar 30 2016 Sean Myers <sean.myers@redhat.com> 2.8.1-0.2.rc
- Pulp rebuild

* Wed Mar 23 2016 Sean Myers <sean.myers@redhat.com> 2.8.1-0.1.beta
- Pulp rebuild

* Fri Mar 04 2016 Dennis Kliban <dkliban@redhat.com> 2.8.0-0.8.beta
- Pulp rebuild

* Thu Mar 03 2016 Dennis Kliban <dkliban@redhat.com> 2.8.0-0.7.beta
- Pulp rebuild

* Thu Mar 03 2016 Dennis Kliban <dkliban@redhat.com> 2.8.0-0.6.beta
- Pulp rebuild

* Fri Feb 19 2016 Dennis Kliban <dkliban@redhat.com> 2.8.0-0.5.beta
- 1626 - Fix yum repo sync cancellation. (ipanova@redhat.com)
- 1659 - ISO Sync is not performed correctly if download policy was changed.
  (ipanova@redhat.com)
- 1660 - Cannot create/update ISO repo without feed. (ipanova@redhat.com)
- 1624 - Repo sync with --retain-old-count is failing (ipanova@redhat.com)

* Thu Jan 28 2016 Dennis Kliban <dkliban@redhat.com> 2.8.0-0.4.beta
- Pulp rebuild

* Tue Jan 19 2016 Dennis Kliban <dkliban@redhat.com> 2.8.0-0.3.beta
- Pulp rebuild

* Wed Jan 13 2016 Dennis Kliban <dkliban@redhat.com> 2.8.0-0.2.beta
- Pulp rebuild

* Mon Jan 11 2016 Dennis Kliban <dkliban@redhat.com> 2.8.0-0.1.beta
- 1264 - UnicodeEncodeError while synchronizing Fedora 21 and 22 updates
  (ipanova@redhat.com)

* Tue Feb 10 2015 Chris Duryee <cduryee@redhat.com> 2.6.0-0.7.beta
- Pulp rebuild

* Tue Feb 10 2015 Chris Duryee <cduryee@redhat.com> 2.6.0-0.6.beta
- 1147073 - when a distribution hasn't changed, sync no longer re-donwnloads
  its files (mhrivnak@redhat.com)

* Fri Jan 16 2015 Chris Duryee <cduryee@redhat.com> 2.6.0-0.5.beta
- 1175616 - Don't index the title field of erratum due to max mongo index size.
  (bcourt@redhat.com)
- 1176698 - Ensure we support Python 2.6 when encoding unicode
  (bcourt@redhat.com)

* Tue Jan 13 2015 Chris Duryee <cduryee@redhat.com> 2.6.0-0.4.beta
- Pulp rebuild

* Mon Jan 12 2015 Chris Duryee <cduryee@redhat.com> 2.6.0-0.3.beta
- 1171278 - allow pulp-admin to print all packages associated with errata
  (cduryee@redhat.com)
- 1171278 - update erratum when a new packagelist is encountered
  (cduryee@redhat.com)

* Tue Dec 23 2014 Chris Duryee <cduryee@redhat.com> 2.6.0-0.2.beta
- 1175818 - Fix failure on Errata with missing "sum" (rbarlow@redhat.com)
- 1171280 - ensure packages are available when calculating applicability
  (cduryee@redhat.com)
- 972880 - The ISO importer now checks all ISO units before downloading new
  content. (jcline@redhat.com)
- 11157852 - Convert timestamp values in the repomd to integers from floats
  (bcourt@redhat.com)
- 1165355 - Sanitize checksum types. (rbarlow@redhat.com)
- 1158945 - Pulp can now publish RPM packages with descriptions containing
  unicode characters. (jcline@redhat.com)
- 1168602 - fix missing /usr/share/pulp-rpm/pulp_distribution.xsd in the spec
  file (bcourt@redhat.com)
- 1151485 - fixing a typo in 2.4 release notes documentation
  (skarmark@redhat.com)

* Mon Dec 22 2014 Randy Barlow <rbarlow@redhat.com> 2.5.2-0.1.rc
- Pulp rebuild

* Fri Dec 19 2014 Randy Barlow <rbarlow@redhat.com> 2.5.2-0.0.beta
- 1175818 - Fix failure on Errata with missing "sum" (rbarlow@redhat.com)
- 1171280 - ensure packages are available when calculating applicability
  (cduryee@redhat.com)
- 1151485 - fixing a typo in 2.4 release notes documentation
  (skarmark@redhat.com)

* Wed Dec 10 2014 Barnaby Court <bcourt@redhat.com> 2.5.1-1
- 11157852 - Convert timestamp values in the repomd to integers from floats
  (bcourt@redhat.com)
- 1165355 - Sanitize checksum types. (rbarlow@redhat.com)
- 1168602 - fix missing /usr/share/pulp-rpm/pulp_distribution.xsd in the spec
  file (bcourt@redhat.com)
- 1165355 - Sanitize checksum types. (rbarlow@redhat.com)
- 1148937 - Repo group publish fails when there are no repo members in the
  group (ipanova@redhat.com)
- 1146294 - do not import pulp.bindings.server to get DEFAULT_CA_PATH
  (cduryee@redhat.com)
- 1073155 - fix permissions in dev setup script (cduryee@redhat.com)
- 1155192 - Fix certificate verification error when set to False
  (contact@andreagiardini.com)
- 1153378 - remove SSLInsecureRenegotation from pulp_rpm.conf
  (cduryee@redhat.com)
- 1151490 - Repo group publish  fails with NoneType error (ipanova@redhat.com)
- 1138475 - yum distributor now always includes "description" element for
  errata (mhrivnak@redhat.com)

* Thu Nov 06 2014 asmacdo <asmacdo@gmail.com> 2.5.0-0.17.rc
- 1155192 - Fix certificate verification error when set to False
  (contact@andreagiardini.com)
- 1153378 - remove SSLInsecureRenegotation from pulp_rpm.conf
  (cduryee@redhat.com)
- 1151490 - Repo group publish  fails with NoneType error (ipanova@redhat.com)
- 1138475 - yum distributor now always includes "description" element for
  errata (mhrivnak@redhat.com)

* Fri Oct 31 2014 Austin Macdonald <amacdona@redhat.com> 2.5.0-0.15.rc
- 1150297 - Replace 2.4.x versions with 2.5.0. (rbarlow@redhat.com)
- 1103232 - Document importer settings. (rbarlow@redhat.com)

* Thu Oct 16 2014 Randy Barlow <rbarlow@redhat.com> 2.4.3-1
- 1103232 - Document importer settings. (rbarlow@redhat.com)

* Mon Oct 13 2014 Chris Duryee <cduryee@redhat.com> 2.4.2-1
- 1150714 - delete old distribution units when syncing (cduryee@redhat.com)

* Sun Oct 12 2014 Chris Duryee <cduryee@redhat.com> 2.5.0-0.8.beta
- 1150714 - delete old distribution units when syncing (cduryee@redhat.com)
- 1049492 - Add docs for the yum_repo_metadata_file. (rbarlow@redhat.com)
- 1139888 - Document the default for validate. (rbarlow@redhat.com)
- 1131260 - Add verify_ssl to repo_auth.conf. (rbarlow@redhat.com)
- 1125388 - ensure we save storage_path when saving units (cduryee@redhat.com)
- 1126960 - support the xml:base attribute on rpm packages in the primary.xml
  for delineating an alternate base location during RPM sync
  (bcourt@redhat.com)
- 1130305 - Document workaround for when migration 3 updates fail.
  (bcourt@redhat.com)
- 1130305 - Document workaround for when migration 3 updates fail.
  (bcourt@redhat.com)
- 1022553 - The 'pulp-admin rpm consumer unbind' command now reports a missing
  binding in a more friendly way (jcline@redhat.com)
- 1130305 - Document workaround for when migration 3 updates fail.
  (bcourt@redhat.com)
- 1127298 - Alternate Content sources needs to wrap the nectar listener in a
  container listener. (bcourt@redhat.com)
- 1127793 - The checksum is now saved to the distributor only if explicitly
  provided (jcline@redhat.com)
- 1128292 - Specify the default attribute on generated package group xml.  This
  fixes a bug where the graphical installer failed to select a default option
  on RHEL 6 if we do not specify a default. (bcourt@redhat.com)
- 1101566 - unit_metadata is now optional for the yum import upload
  (jcline@redhat.com)
- 1108306 - Adjust the location tag in the primary xml snippet during repo
  sync.  This was previously only done during upload. (bcourt@redhat.com)
- 1118501 - updating logic to form consumer profile lookup table with the
  newest rpm, so that in case of multiple packages with same name and arch,
  applicability logic does not fail (skarmark@redhat.com)

* Tue Sep 23 2014 Randy Barlow <rbarlow@redhat.com> 2.4.1-1
- 1131260 - Add verify_ssl to repo_auth.conf. (rbarlow@redhat.com)
- 1135144 - certificate verified by apache. (jortel@redhat.com)
- 1130312 - Add release notes for 2.4.1. (rbarlow@redhat.com)
- 1131260 - use platform openssl for certificate verification.
  (jortel@redhat.com)
- 1118501 - updating logic to form consumer profile lookup table with the
  newest rpm, so that in case of multiple packages with same name and arch,
  applicability logic does not fail (skarmark@redhat.com)

* Sat Aug 09 2014 Randy Barlow <rbarlow@redhat.com> 2.4.0-1
- 1121264 - correcting the documentation for max_speed (mhrivnak@redhat.com)
- 1116060 - Fix handling of failed package installs. (jortel@redhat.com)
- 1097816 - adding "gpgkey" as a valid distributor config value
  (mhrivnak@redhat.com)
- 1111322 - Fix client side error trying to update iso repo (bcourt@redhat.com)
- 1099771 - Add a unit test to assert correct behavior for reporting invalid
  checksums. (rbarlow@redhat.com)
- 973784 - improving performance of depsolve (mhrivnak@redhat.com)
- 1107117 - Viewing the details of an erratum using "pulp-admin rpm repo
  content errata --repo-id=<Repo ID> --erratum-id=<errata id>" now behaves as
  expected (jcline@redhat.com)
- 1101622 - Erratum uploads from pulp-admin now stop when malformed csv files
  are found (jcline@redhat.com)
- 995082 - 'pulp-admin rpm repo list --details' now displays all distributors
  attached to a repository (jcline@redhat.com)
- 1104839 - pulp no longer creates a prestodelta.xml file if there are no DRPMs
  to publish (mhrivnak@redhat.com)
- 1099600 - fix treeinfo files during upgrades (cduryee@redhat.com)
- 1097790 - check task details of erratum upload to determine if task succeeded
  (cduryee@redhat.com)
- 1102377 - generating listing files during repo publish (mhrivnak@redhat.com)
- 1100027 - eliminating race condition during listing file generation
  (mhrivnak@redhat.com)
- 1101168 - use metadata when computing RPM filename (cduryee@redhat.com)
- 1100848 - Only hand strings to ElementTree. (rbarlow@redhat.com)
- 1082386 - Added better logging detail to yum syncs. (rbarlow@redhat.com)
- 1095332 - updated the position of checking for existing units and associating
  them with repo, so that the progress calculations are not affected
  (skarmark@redhat.com)
- 1094498 - Added logic to re-download rpms, drpms and srpms that don't exist
  on disk during synchronization (skarmark@redhat.com)
- 1096931 - improving repo update command to better detect spawned tasks
  (mhrivnak@redhat.com)
- 1051700 - Don't build plugins or admin extensions on RHEL 5.
  (rbarlow@redhat.com)
- 1099236 - add Obsoletes for python-pulp-rpm-extension (cduryee@redhat.com)
- 1098844 - updating yum distributor to publish rpms at the same level as
  repodata directory and not as per relative path of each unit
  (skarmark@redhat.com)
- 1095437 - convert checksum-type keyword to checksum_type (bcourt@redhat.com)
- 1042932 - Update to use the step processor for exporting repos and repo
  groups (bcourt@redhat.com)
- 1097434 - The profile translates erratum to rpm unit keys.
  (rbarlow@redhat.com)
- 1097813 - post-upload linking of errata to rpms now works
  (mhrivnak@redhat.com)
- 1095829 - strip repomd.xml from treeinfo when appropriate
  (cduryee@redhat.com)
- 1096931 - removed CLI's attempt to display data that no longer exists
  (mhrivnak@redhat.com)
- 1093429 - Changing parameter name for repo create due to API change
  (mhrivnak@redhat.com)
- 1080455 - fixing rendering error in pulp-consumer bind and unbind commands
  (skarmark@redhat.com)
- 1094404 - Fix to not delete all repo contents accidentally.
  (bmbouter@gmail.com)
- 1090534 - Publish the repomd.xml file. (rbarlow@redhat.com)
- 1082245 - Fix failed task reporting in content install commands.
  (jortel@redhat.com)
- 1091078 - rhui cataloger requires nectar >= 1.2.0. (jortel@redhat.com)
- 1085087 - fixing yum importer so that packages are not re-downloaded for
  every repository (skarmark@redhat.com)
- 1062725 - package install fails when requested package not available.
  (jortel@redhat.com)
- 1085853 - Moved logger statement out of the for loop so that it doesn't get
  printed for every rpm migrated (skarmark@redhat.com)
- 1065016 - Don't require optionlist to be present. (rbarlow@redhat.com)
- 1025465 - Log all ISO download failures. (rbarlow@redhat.com)
- 1084077 - removing python-pulp-rpm-extension from admin and consumer
  extension deps as we no longer produce this rpm (skarmark@redhat.com)
- 1081865 - updating location element in the repomd file to include href
  attribute (skarmark@redhat.com)
- 1083098 - Fix rpm handler loading. (jortel@redhat.com)
- 973784 - refactored dependency solving workflow for performance
  (mhrivnak@redhat.com)
- 1070336 - Fix passing of the consumer group id when the --all option is used
  for the "pulp-admin rpm consumer group package update ..." command
  (bcourt@redhat.com)
- 1067169 - Fixed the copy command so it outputs the result without crashing
  (mhrivnak@redhat.com)
- 1064594 - initializing plugin loader for migration 0015 (mhrivnak@redhat.com)
- 1042932 - Fix listings files in export distributor for both individual repos
  and repo groups. (bcourt@redhat.com)
- 1046160 - giving up ownership of /var/lib/pulp/published
  (mhrivnak@redhat.com)
- 1053674 - implement distributor_removed on yum distributor
  (bcourt@redhat.com)
- 1056243 - Implement yum distributor create_consumer_payload (fix consumer
  binding) (bcourt@redhat.com)
- 921743 - Adjust ownership and permissions for a variety of the RPM paths.
  (rbarlow@redhat.com)
- 1034978 - Move to standard formatter for unit copy & remove extension
  (bcourt@redhat.com)
- 1038309 - Fix bug where distributor type was being checked against the
  distributor id instead of the type id (bcourt@redhat.com)
- 1029057 - Save the rpm repo checksum type from the repo scratchpad to the
  distributor config during a publish. (bcourt@redhat.com)
- 1029057 - Save the rpm repo checksum type from the repo scratchpad to the
  distributor config during a publish. (bcourt@redhat.com)
- 1003965 - Error out of a sync if there is no feed url (bcourt@redhat.com)
- 995076 - make sure to call finalize on the nectar config object
  (jason.connor@gmail.com)
- 1004580 - Add the ability to specify the checksum type when uploading rpm &
  srpm units (bcourt@redhat.com)
- 1023188 - Create listing files in ISO export distributor (bcourt@redhat.com)
- 1032189 - fixed use of gettext with multiple substitutions
  (mhrivnak@redhat.com)
- 1004981 - RPM agent should support filtering packages by epoch, version,
  release, and architecture when installing (bcourt@redhat.com)
- 924788 - Added upload SRPM command (jason.dobies@redhat.com)
- 1020460 - Fixed removing skip list from an existing repository
  (jason.dobies@redhat.com)

* Mon Nov 25 2013 Barnaby Court <bcourt@redhat.com> 2.3.1-1
- 1034366 - Failure to export RPM repositories to ISO where the repository does
  not have a checksum manually set. (bcourt@redhat.com)
- 1033776 - If scratchpad contains fields other than checksum_type then
  checksum may be calculated incorrectly. (bcourt@redhat.com)

* Tue Nov 19 2013 Barnaby Court <bcourt@redhat.com> 2.3.0-1
- 1029057 - Save the rpm repo checksum type from the repo scratchpad to the
  distributor config during a publish. (bcourt@redhat.com)
- 1029057 - override sha with sha1 in order to support yum modifyrepo command.
  (bcourt@redhat.com)
- 1029057 - Set checksum for metadata from upstream repository on synced
  repositories. (bcourt@redhat.com)
- 1026907 - Fix dep equality comparison when a release is omitted.
  (jason.dobies@redhat.com)
- 1020007 - added loading of conf file to entry point (jason.connor@gmail.com)
- 1018235 - Docs about how a repo URL is generated. (jason.dobies@redhat.com)
- 1021672 - Ensure that if the treeinfo specifies a packagedir that the
  directory is created and a link to all the packages can be found within it
  (bcourt@redhat.com)
- 1008010 - fixed parsing of the translated names and descriptions for groups
  and categories during import (mhrivnak@redhat.com)
- 1020415 - added a workaround for a bug in yum where it neglects to encode
  epochs to strings, which in rare circumstances could cause a failure to
  generate updateinfo.xml (mhrivnak@redhat.com)
- 973678 - Return a report when ISO uploads are processed. (rbarlow@redhat.com)
- 975503 - Add pulp-admin iso repo publish status command (bcourt@redhat.com)
- 999129 - create and use unique subdirectories for rpm and iso uploads
  (skarmark@redhat.com)
- 1011267 - Display checksum validation errors via the RPM command line client
  (bcourt@redhat.com)
- 962928 - adding repo feed validation in iso_importer to raise a more graceful
  error message than random traceback (skarmark@redhat.com)
- 965751 - the iso importer now uses the threaded requests downloader instead
  of the curl downloader (mhrivnak@redhat.com)
- 976435 - load puppet importer config from a file using a common method.
  (bcourt@redhat.com)
- 979589 - fixing consumer update for all packages failing with  KeyError:
  'resolved' (skarmark@redhat.com)
- 1004790 - Remove legacy dependency on Grinder that is no longer required.
  (bcourt@redhat.com)
- 953248 - Custom checksum on repository config was not honored.
  (bcourt@redhat.com)
- 973744 - when doing recursive copies, all copied units are now displayed, not
  just the ones that were explicitly matched by the request.
  (mhrivnak@redhat.com)
- 972913 - adding cli validation for conditional packages when upload a package
  group (skarmark@redhat.com)
- 973678 - Do not allow ISOs named PULP_MANIFEST to be uploaded.
  (rbarlow@redhat.com)
- 997177 - Move uploads to the content directory instead of copying them
  (bcourt@redhat.com)
- 976845 - updating descriptions for iso repo sync and publish commands as both
  don't support status sub-command (skarmark@redhat.com)
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

* Mon Jul 15 2013 Jeff Ortel <jortel@redhat.com> 2.2.0-1
- 984104 - fixed a bug that caused multiple calls to group copy with the
  --recursive option to fail (mhrivnak@redhat.com)
- 983323 - fixed an XML parsing incompatibility with python 2.6 where the
  default XML namespace was being mishandled. (mhrivnak@redhat.com)
- 982649 - fixing a python 2.6 incompatibility which caused writing of XML for
  individual packages to fail. (mhrivnak@redhat.com)
- 976042 - source RPMs are now categorized correctly as type "srpm".
  (mhrivnak@redhat.com)
- 980572 - can now import groups from comps.xml files where some groups entries
  don't include a "uservisible" value, such as in a Fedora 18 repo.
  (mhrivnak@redhat.com)
- 973402 - fixed a mishandling of XML namespaces in repo metadata that led to
  problems when installing packages with dependencies from a published repo.
  (mhrivnak@redhat.com)
- 976333 - Fixed importer config look up to use constant
  (jason.dobies@redhat.com)
- 976333 - Updated the relative URL calculation to use the new key for feed
  (jason.dobies@redhat.com)
- 974663 - the importer can now save repo metadata files of unknown types in
  the database as units (mhrivnak@redhat.com)
- 972909 - Extract the provides/requires fields from the XML server-side.
  (jason.dobies@redhat.com)
- 973387 - fix fsize attribute error on unit install progress reporting.
  (jortel@redhat.com)
- 972909 - invalid requires and provides data originally generated by the v2.1
  upload workflow now gets corrected by a migration. (mhrivnak@redhat.com)
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
- 950690 - Removed copy commands that aren't supported in the plugin
  (jason.dobies@redhat.com)
- 966178 - Added default to remove-missing (jason.dobies@redhat.com)
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
- 953665 - added the ability for copy operations to not also copy child units,
  such as a group copying its RPMs. Also restricted the fetching of existing
  units to their unit key fields, which reduced RAM use tremendously. Copying a
  RHEL6 repo went from using about 4.3GB of RAM to < 100MB.
  (mhrivnak@redhat.com)
- 928084 - The ISOImporter now handles malformed PULP_MANIFEST files.
  (rbarlow@redhat.com)
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

* Mon Mar 04 2013 Jeff Ortel <jortel@redhat.com> 2.1.0-1
- 902514 - removed the <VirtualHost *:80> block in favor of using the
  platform's authoritative one. (mhrivnak@redhat.com)
- 916336 - Change the default num_threads to 4. (rbarlow@redhat.com)
- 913172 - Fixed a section heading and added info about configuring a proxy for
  global use (mhrivnak@redhat.com)
- 889565 - Corrected configuration options from being flags to options
  (jason.dobies@redhat.com)
- 905119 - Remove unused /ks alias from the pulp_rpm.conf file.
  (rbarlow@redhat.com)
- 700945 - Include changelog and filelist info as part of rpm metadata
  (pkilambi@redhat.com)
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

* Thu Dec 20 2012 Jeff Ortel <jortel@redhat.com> 2.0.6-1
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
- 876174 - Migrated over missing consumer commands (jason.dobies@redhat.com)
