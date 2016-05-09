The Origin of RPM Content
=========================

Overview
--------

Pulp supports importing and publishing RPM content, but where does all this
content come from? Who is generating it, and with what tools? The answer to
these questions are answered in this document. Note that this document
only covers Fedora and Red Hat Enterprise Linux. It does not cover SLES,
OpenSuse, Scientific Linux, CentOS, Oracle Linux, or any other RPM-based
distributions (yet).


The RPM
-------

RPM is a packaging format. Many Linux distributions use RPM to distribute their
software packages. An RPM is a collection of metadata about the package as well
as a payload. What the payload contains depends on the type of RPM. There are
three different types of RPM:

 * Source code RPMs (referred to as "SRPMs", ".src.rpm" file extension)

 * Binary RPMs (referred to as "RPMs", ".rpm" file extension)

 * Binary delta RPMs (referred to as "DRPMs", ".drpm" file extension)

What each RPM contains is completely up to the creator of the RPM package. It
could, for example, contain an entire operating system. However, this is very
unweildy. Many distributions (Fedora, Red Hat, etc.) have strict packaging
guidelines about what should be included. The long version can be found on the
Fedora Wiki
`Package Guideline <https://fedoraproject.org/wiki/Packaging:Guidelines>`_,
but the short version is that each RPM should contain at most a single software
project (for example, the Linux kernel, GCC, or binutils). Generally, if
documentation is large it is separated into its own RPM. If the software
project is compiled, debugging symbols are packaged separately as well. This
means there can be several RPMs for a single project.

File Format
^^^^^^^^^^^

The RPM file format consists of a "lead" which identifies the file as an RPM, a
"signature" section which can be used to ensure the integrity and authenticity
of the RPM (via GPG), a "header" section which contains metadata about the
packaged software (name, version, architecture, file list, etc.), and a
"payload" which is a file archive (usually in the cpio format) compressed with
gzip.

SRPM
^^^^

The payload of a source RPM is simply a compressed tarball of source code and a
file, called a spec file, that describes how to turn the source RPM into a
binary RPM. The spec file includes the installation location and permissions
for all files in the package. This allows the RPM tool to install
the binary RPM to a system with the correct permissions and track which package
"owns" which files. Spec files also allow the author to run shell scripts before
or after an installation, removal, or upgrade of a package. The source RPM can
be built into one or more binary RPMs using ``rpmbuild``.

RPM
^^^

A binary RPM's payload is the collection of files installed from the build
process of the source code. It is architecture and distribution-specific.
If a package happens to be architecture-independent, it can declare its
architecture as ``noarch``.

DRPM
^^^^

A binary delta RPM has a payload which contains the binary diff between two
releases of the same package. For example, there could be a binary delta RPM
that can be used to upgrade an existing Firefox 45 installation to a Firefox
46 installation without downloading the entire binary RPM for Firefox 46. This
format exists to save bandwidth for content provides and requires a significant
amount of computation on the client attempting to install the DRPM. Unlike RPMs
and SRPMs, DRPMs are not created by ``rpmbuild``. Other tools exist to build
them, like `deltarpm <https://github.com/rpm-software-management/deltarpm>`_,
or `createrepo_c <https://github.com/rpm-software-management/createrepo_c>`_
which leverages the  `drpm library <https://git.fedorahosted.org/git/drpm.git>`_.
When using createrepo_c, it is possible to generate DRPMs and the prestodelta.xml
metadata required for an RPM repository (covered below).


The Yum/RPM Repository
----------------------

RPM provides a packaging format, but the RPM (often referred to as yum)
repository provides a way to distribute them. An RPM repository consists of one
or more RPM packages and some metadata describing what RPM packages the
repository contains. The metadata, usually located in a directory called
"repodata" in the root of the repository, is contained in several XML and/or
optionally several SQLite files. DNF does not make use of the SQLite databases
(which contain the same metadata as the XML), although some clients might. The
filenames of each of these metadata files can be arbitrary, so clients locate
them by using a metadata file that describes the metadata: the repomd.xml file.

To create an RPM repository, all that is required is that the repomd.xml,
primary.xml, filelists.xml, and other.xml metadata files be present. There are
two libraries that can do this: createrepo, and
`createrepo_c <https://github.com/rpm-software-management/createrepo_c>`_.
createrepo is a Python library that is no longer maintained. createrepo_c
is a C library with Python bindings that is actively maintained.

repomd.xml
^^^^^^^^^^

repomd.xml is the metadata file that clients use to discover what repository
metadata files exist in the repository. It should always be located at
``repodata/repomd.xml`` relative to the root of the repository. It references the
location of all other metadata files for the repository. This means that the
other metadata files might not be located in the ``repodata/`` directory, but it
is convension to store all RPM repository metadata in ``repodata/`` and all
current Fedora, Red Hat, and CentOS repositories do this.

The repomd.xml file (XML namespace: http://linux.duke.edu/metadata/repo which is
sadly a dead link) contains ``data`` elements with one attribute, ``type``. The
``type`` attribute is a string which references the type of metadata file the
``data`` element refers to. Common values are ``group``, ``filelists``, ``group_gz``,
``primary``, ``other``, ``filelists_db``, ``primary_db``, and ``other_db``. ``<thing>_db``
refer to SQLite versions of the metadata, while those sans ``_db`` refer to XML
versions. Each ``data`` element contains several other elements describing the
metadata and where it is located: ``checksum``, ``location``, ``timestamp``, and
``size`` seem to be always present, with ``open-size``, ``open-checksum``, and
``database_version`` potentially appearing as well.


primary.xml
^^^^^^^^^^^

The primary.xml file (often stored in ``repodata/<file-checksum>-primary.xml.gz``)
contains a list of every RPM and SRPM package (DRPMs are covered by
prestodelta.xml below) in the repository (and the network location to download
them). This includes information like the name, epoch  version, release, and
architecture. It also lists what libraries and binaries the package provides, as
well as what libraries and binaries the package depends upon to work. This
metadata can be used by the client to determine the dependency tree of a
package, how much data it will need to download, and how much space the packages
will take up when installed. Try doing ``yum install <some uninstalled package>``
some time and note how it describes what it's going to install for dependencies
and how much space it's going to take up. All that comes from this metadata
file.


filelists.xml
^^^^^^^^^^^^^

The filelists.xml metadata does exactly what the name implies. It is a list of
every single file contained in each RPM package. Like the primary.xml file, it
contains a list of ``package`` elements (which references packages from the
primary.xml file), within which there are a number of ``file`` elements, as well
as a ``version`` element that identifies the package version. Files that are
directories have a ``type=dir`` attribute.


other.xml
^^^^^^^^^

The other.xml contains... well, other information about each package. It
references each package in much the same way as filelists.xml. At the very
least, it contains ``changelog`` elements, where an element exists for each
changelog entry in the spec file used to build the RPM. Typically this is
truncated, often to the 10 most recent releases.


comps.xml
^^^^^^^^^

comps.xml contains, among other things, a list of groups. Each group contains
a description and a list of packages in that group. Packages can be marked as
mandatory, default, or optional, based on the value of the ``type`` attribute
on the ``packagereq`` element.

Additional metadata in comps.xml are package environments and categories, which
are simply a list of package groups, and langpacks.


prestodelta.xml
^^^^^^^^^^^^^^^

prestodelta.xml is used to describe the DRPMs a repository contains. A DRPM is
built from two different binary RPMs (a new version and an old version). A
repository can, and often does, contain several DRPMs for various upgrade paths.
For example, there might be a DRPM containing the difference between
firefox-45.0 and firefox-46.0, as well as a DRPM containing the difference
between firefox-45.1 and firefox-46.0. A client must retrieve the correct DRPM
for the version of a package it currently has installed to apply the DPRM.

The ``prestodata`` root element contains zero or more ``newpackage`` elements. Each
``newpackage`` element has ``name``, ``epoch``, ``version``, ``release``, and ``arch``
attributes to identify what the new version of the package is.

Each ``newpackage`` element contains one or more ``delta`` elements. The ``delta``
element has the ``oldepoch``, ``oldversion``, and ``oldrelease`` attributes to
identify which old version of the package the DRPM applies to.

Each ``delta`` element contains 4 elements: ``filename``, ``sequence``, ``size``, and
``checksum``.

For example::

  <?xml version="1.0" encoding="UTF-8"?>
  <prestodelta>
      <newpackagename="cmake-fedora" epoch="0" version="2.6.0" release="1.fc23" arch="noarch">
          <delta oldepoch="0" oldversion="2.3.4" oldrelease="2.fc23">
              <filename>drpms/cmake-fedora-2.3.4-2.fc23_2.6.0-1.fc23.noarch.drpm</filename>
              <sequence>cmake-fedora-2.3.4-2.fc23-84bdd3315d4caddf8245e82cb83de4e301d5</sequence>
              <size>51194</size>
              <checksum type="sha256">6926544188f70d0e9dbedfd07fcf361d6fdc813d2888f5635fd647069bcc14ed</checksum>
          </delta>
          <delta oldepoch="0" oldversion="2.5.1" oldrelease="1.fc23">
              <filename>drpms/cmake-fedora-2.5.1-1.fc23_2.6.0-1.fc23.noarch.drpm</filename>
              <sequence>cmake-fedora-2.5.1-1.fc23-9930049f7b6f6c78a7732f5230c38f6e0196</sequence>
              <size>34154</size>
              <checksum type="sha256">45012a502babf1bdda402c05b50c1c68f8c5dbe62d85ce61a0a41c71c0ec6f8c</checksum>
          </delta>
      </newpackagename>
  </prestodelta>


updateinfo.xml
^^^^^^^^^^^^^^

updateinfo.xml describes errata. An erratum describes a change in an RPM
repository. Errata are typically divided into three categories: security,
bugfix, and enhancement. If a package is being updated to fix a security
problem, the erratum for that update is a security erratum. If it is simply a
bug with no (known) security implications, it is a bugfix erratum. Finally, the
update could be to provide additional features, in which case it is an
enhancement erratum.

In Fedora, the updateinfo.xml metadata is generated by
`Bodhi <https://github.com/fedora-infra/bodhi/>`_. It is created when an update
is pushed by Bodhi and injected into the RPM repository metadata using the
modifyrepo_c tool, part of the createrepo_c package.

What errata reference vary from project to project and product to product. For
example, Red Hat Enterprise Linux and CentOS issue an erratum per component
(SRPM package). However, other projects and products might issue a single
erratum for many components at once. Therefore, an erratum references a list of
one or more RPM packages since one SRPM can produce many RPM packages.

Each errata has a ``pkglist`` element, which contains a ``collection`` element,
which contains a ``name`` element and one or more ``package`` elements. Each package
element has ``name``, ``version``, ``release``, ``epoch``, and ``arch`` attributes to
identify the affected package. In addition to those attributes, there is a ``src``
attribute. In RHEL errata, this appears to be the name of the SPRM::

  <package name="java-1.7.0-openjdk" version="1.7.0.55" release="2.4.7.2.el7_0" epoch="1" arch="x86_64" src="java-1.7.0-openjdk-1.7.0.55-2.4.7.2.el7_0.src.rpm">

However, in Fedora this ``src`` field references where the package is located by URL::

  <package name="opendnssec" version="1.4.9" release="1.fc23" epoch="0" arch="i686" src="https://download.fedoraproject.org/pub/fedora/linux/updates/23/i386/o/opendnssec-1.4.9-1.fc23.i686.rpm">

Each ``package`` element contains a ``filename`` element, and in RHEL errata, a
``sum`` element.


Organizing RPM Builds
---------------------

As you now know from the RPM section, each package requires a source tarball and
a spec file. In addition to these two required files, a packager may create
patch files that alter the source code in some way. This is done for many
reasons, but generally it is done to work around a bug in the upstream project,
back-port a bugfix from upstream, or unbundle libraries. All this can become
unwieldy to manage and track, especially when dealing with thousands of packages
(Fedora contains ~18,000 packages). Fedora uses
`dist-git <https://github.com/release-engineering/dist-git>`_ to solve this problem.

dist-git is designed specificly to manage RPM package sources. It stores the
spec file, patches, and a reference to the source tarball in a git repository.
The source tarball itself is not checked into Git and instead lives in a
lookaside cache. The validity of the source tarball is determined by the
reference checked into the git repository. Each package is contained in its own
dist-git repository. This allows package maintainers to collaborate and view the
history of a package.

Of course, having the sources, patches, and spec files organized doesn't help
much if the RPMs have to be built manually.
`Koji <https://fedoraproject.org/wiki/Koji>`_ (and to some extent
`Copr <https://copr.fedorainfracloud.org/>`_ is a tool to build and track SRPMs
and RPMs from those dist-git repositories. It performs the builds in clean, secure
environments for many different architectures by using
`Mock <https://fedoraproject.org/wiki/Mock>`_. Each build can be tagged to help
track where each build ends up. This is helpful when we want to turn a
collection of packages into an operating system distribution. An example of a
tag would be ``f24``, ``f24-updates``, or ``f24-updates-candidate``.


Composes
--------

Having all the packages built and tracked in a tool like Koji is only helpful if
there are tools to turn those packages into useful, consumable content. What is
useful content?

 * RPM repositories from which packages can be installed

 * Installation media (ISOs for CD/DVD, PXE boot images, USB boot images, etc)

 * Arbritrary additional files such as release notes, licenses, EULA, GPG keys,
   and branding images.


Fedora and RHEL have the concept of a
`compose <http://release-engineering.github.io/productmd/terminology.html#compose>`_.
A set of packages make of a product release (Fedora 24, for example). The set of
packages used in a compose can be controlled by the tag a package has in Koji.
As a release is developed, new packages are added and current packages are
updated or removed. A compose is an immutable snapshot at a certain point in
time of a product release's development. At some point, the compose is deemed to
be "gold" and becomes the GA release of a product. For example, Fedora 23 is a
release of the Fedora product.

A compose contains one or more variants. A
`variant <http://release-engineering.github.io/productmd/terminology.html#variant>`_
is a particular subset of the set of packages used in the compose. One subset
might target servers, another workstations, and another Atomic hosts. Each
variant is built for one or more architectures (i686, x86_64, sparc, ppc64, etc).

Each of these variant builds for a specific architecture are referred to as
`trees <http://release-engineering.github.io/productmd/terminology.html#tree>`_. A
tree is made up of:

 * One or more RPM repositories

 * Bootable ISO images

 * PXE boot images including EFI boot files, ISOLINUX boot files, and one or
   more kernel images with initial RAM disks.


Almost all the content in a tree is described in a metadata file called the
`treeinfo <http://release-engineering.github.io/productmd/treeinfo-1.0.html>`_
file (sometimes ``.treeinfo``), which is located in the root of the tree
directory. This metadata file can be parsed using the Red Hat Release
Engineering tool, `productmd <https://github.com/release-engineering/productmd>`_.

To summarize, a compose is made up of variants, which are made of
architecture-specific trees.

The tool used by Fedora to create composes is called
`Pungi <https://pagure.io/pungi>`_. Pungi makes use of the `Lorax
project <https://github.com/rhinstaller/lorax>`_ to build each tree. Prior to the
Lorax project, trees were generated  by scripts in the `Anaconda installer
<https://github.com/rhinstaller/anaconda/>`_. These scripts have been
`removed <https://github.com/rhinstaller/anaconda/commit/4a74482d61764221d71bc273d2c3e6544b079332>`_
since Lorax replaces them.

As a concrete example, the Red Hat Enterprise Linux 6.7 (release) Server
(variant) x86_64 tree contains the following:

 * The RPM repository (metadata in ``repodata/``)

 * Several addon RPM repositores (metadata in ``HighAvailablility/repodata/``,
   ``LoadBalancer/repodata/``, ``ResilientStorage/repodata/``, and
   ``ScalableFileSystem/repodata/``)

 * EFI/BOOT/BOOTX64.conf: EFI configuration containing references to the kernel
   and initrd in ``images/pxeboot/``

 * EFI/BOOT/BOOTX64.efi: EFI boot file for x86_64 architecture

 * EFI/BOOT/splash.xpm.gz: boot splash screen graphic

 * images/efiboot.img: CD/DVD boot image for EFI systems

 * images/efidisk.img: USB boot image for EFI systems (can be dd'ed to a USB
    flash drive)

 * images/boot.iso: Bootable ISO image built from the various images in
   ``images/``, ``EFI/``, ``isolinux/``

 * images/install.img: Stage 2 Installation image, loaded when you start the
   installation from a supported boot method.

 * images/product.img: RHEL product description information used in the
   installer

 * images/pxeboot/initrd.img: Initial ramdisk file for PXE-capable systems

 * images/pxeboot/vmlinuz: Kernel image for PXE-capable systems

 * isolinux/: bootloader with configuration, as well as a kernel image, initial
   RAM disk, and memtest.

In the above example the ``EFI/`` and ``isolinux/`` directories are not referenced
by metadata as they are `not required by any client
<https://bugzilla.redhat.com/show_bug.cgi?id=1335160#c1>`_.


Updates
-------

Composes are immutable, and when a product is released, it does not change.
Updates are provided in the form of `errata <https://en.wikipedia.org/wiki/Erratum>`_.
When a package is updated, an erratum must be associated with it. An erratum is
metadata about the update of one or more packages, very much like the erratum for
a book. These are described in the updateinfo.xml file in an RPM repository. In
the case of Fedora and RHEL, the RPM repositories in the compose are kept pristine
and unchanged, but this is not enforced by the tooling, it is merely convention.
There may be distributions out there that add their errata and updated RPM packages
to the GA compose.

Fedora provides an excellent example of this method. When a release is made,
it is located under the ``released/`` directory on the mirrors. For example, the
Fedora releases lives in ``releases/<release-version>/<variant>/<arch>/``. This
repository remains unchanged, even after updates are released for Fedora. You'll
notice in the ``repodata`` directories, there is no updateinfo.xml. Updates are
provided under ``updates/<release-version>/<arch>/``. This RPM repository does
contain updateinfo.xml, which is the errata for all the packages in this repository.

Red Hat Enterprise Linux is similar, except that releases are usually stored in
the ``rhel/<variant>/<major-release>/<minor-release>/<arch>/kickstart/``
repository. Updates are provided in the
``rhel/<variant>/<major-release>/<minor-release>/<arch>/os/`` repository.


Overview of the Fedora Build Process
------------------------------------

To get an idea of how this works in practice, the Fedora build process is outlined
below. The Fedora Release Engineering team has written `documentation on their release
process <https://docs.pagure.org/releng/index.html>`_ which may be helpful to reference.

The basic workflow is as follows:

1. Packages are created from upstream repositories (Git repositories, PyPi,
   RubyGems, etc.) by creating a spec file and any necessary patches. These go
   through a review process. Once approved, a dist-git repository is created for
   the package and the spec file with patches are checked in. The source tarball
   is uploaded to a lookaside cache (it is not checked into source control, but
   a method of verifying the tarball is).

2. Packages are built in Koji by the package maintainer. Each build is made for
   a Koji build target. A build target specifies where a package should be built
   and how it  should be tagged afterwards. This allows target names to remain
   fixed as  tags change through releases.

3. Products are composed using Pungi. This creates ISOs and other installation
   media, boot images for PXE,  etc.

4. At a certain point in the release cycle, `Fedora's Bodhi <https://bodhi.fedoraproject.org/>`_
   is turned on. After a package is built (step 2), the package maintainer submits
   the build to Bodhi. It is available for testing in the updates-testing repository
   and community members can +1 or -1 updates. After a certain period of time or
   enough +1, the package is approved. It is pushed into the updates repository with
   an entry in the updateinfo.xml metadata file.

