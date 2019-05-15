Features
========

RPM Support includes a number of features that are not found in the generic
Pulp platform, the most important of which are described below.

Types
-----

Pulp RPM supports the following types:

* RPM
* DRPM
* SRPM
* Erratum
* Distribution
* Package Group
* Package Category
* Modules and module defaults

Errata
^^^^^^

.. push count? what is that?

`Red Hat <http://www.redhat.com>`_ provides security, bug fix, and enhancement
updates for supported Red Hat Enterprise products. These security updates are
provided through the Red Hat CDN, and are described by errata. Pulp supports
these errata types with a number of related features.

Errata are synchronized from upstream repositories. Errata can also be
:ref:`copied <copy-errata-recipe>` from one repository to another.
Administrators can also :ref:`upload <create-errata-recipe>` their own errata to
a repository. Please see the :doc:`recipes` documentation to learn how to
perform these operations.

Modularity
^^^^^^^^^^

Pulp supports the following modularity_ repository content management use cases:

* synchronization of the modularity metadata content, the
  ``repodata/*modules.yaml.gz`` file, with either immediate or
  on-demand synchronization

* publication of the modularity metadata with the repository publication

* copy of one or more modules and/or module defaults between the repositories

* removal of one or more modules and/or module defaults from the repository;
  RPMs related to a module are also removed to preserve consistency of a module

* upload of one or more modules and/or module defaults into the repository

* modules published through Pulp are consumable by the ``dnf`` client

.. _modularity: https://docs.pagure.org/modularity/

Boolean (rich) dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Pulp supports RPM content with `boolean dependencies
<http://rpm.org/user_doc/boolean_dependencies.html>`_ in these basic repository
and content management use cases:

* synchronization, publication and content upload

* copying content between repositories

* displaying boolean dependencies

* providing the content to the ``dnf`` client to process boolean dependencies


.. _advanced_copy_between_repositories:

Advanced copy between repositories
----------------------------------

There are content types in RPM plugin which relate to each other in some way,
so there are use cases when not only a specific content unit should be copied
but also content units related to it. In such cases a ``recursive`` flag should
be used during `copy operation <https://docs.pulpproject.org/dev-guide/integration/rest-api/content/associate.html?highlight=recursive#copying-units-between-repositories>`_.

In a simple case the result of such API call copies unit and units directly related to it.
There are more complicated relations and behavior may vary depending on the content
and the type of a recursive flag. More information about such cases below.

RPM dependencies
^^^^^^^^^^^^^^^^
An RPM can depend on other RPMs. 

::

   dependencies: foo.rpm -> bar.rpm -> baz.rpm

   repo A
     |
     |----foo-1.0.rpm
     |----bar-1.0.rpm
     |----baz-1.0.rpm


   repo B
     |
     |----bar-0.7.rpm


| Use case #1: copy RPM itself
| Flag to use: None

::

    Result of copying foo-1.0.rpm from repo A to repo B:

    repo B
     |
     |----foo-1.0.rpm
     |----bar-0.7.rpm


| Use case #2: copy RPM and *all* its *latest* RPM dependencies
| Flag to use: ``recursive``

::

    Result of copying foo-1.0.rpm from repo A to repo B:

    repo B
     |
     |----foo-1.0.rpm
     |----bar-0.7.rpm
     |----bar-1.0.rpm
     |----baz-1.0.rpm


| Use case #3: copy RPM and its *latest missing* RPM dependencies
| Flag to use: ``recursive_conservative``

::

    Result of copying foo-1.0.rpm from repo A to repo B:

    repo B
     |
     |----foo-1.0.rpm
     |----bar-0.7.rpm
     |----baz-1.0.rpm


Modules and their artifacts (RPMs), simple case
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| A Module lists artifacts it consists of.
| Simple case (no RPM dependencies, no module dependencies).

::

   module-FOO: [foo-1.0.rpm]

   repo A
     |
     |----module-FOO
     |----foo-1.0.rpm


   repo B
     |
     |----bar-0.7.rpm


| Use case #1: copy module itself (and all its available artifacts are copied as well)
| Flag to use: None

::

    Result of copying module-FOO from repo A to repo B:

    repo B
     |
     |----module-FOO
     |----foo-1.0.rpm
     |----bar-0.7.rpm

    All available artifacts are copied, always. There is no way to copy just module on its own,
    if any of its artifacts are present in a source repo (repo A).


Modules and their artifacts (RPMs), complicated case 1
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| A Module lists artifacts it consists of.
| Complicated case 1 (RPM dependencies, no module dependencies).

::

   dependencies: foo.rpm -> bar.rpm -> baz.rpm
   module-FOO: [foo-1.0.rpm]

   repo A
     |
     |----module-FOO
     |----foo-1.0.rpm
     |----bar-1.0.rpm
     |----baz-1.0.rpm

   repo B
     |
     |----bar-0.7.rpm


| Use case #1: copy module and its artifacts and artifacts' *latest* dependencies
| Flag to use: ``recursive``

::

    Result of copying module-FOO from repo A to repo B:

    repo B
     |
     |----module-FOO
     |----foo-1.0.rpm
     |----bar-0.7.rpm
     |----bar-1.0.rpm
     |----baz-1.0.rpm

| Use case #2: copy module and its artifacts and artifacts' *missing* RPM dependencies
| Flag to use: ``recursive_conservative``

::

    Result of copying module-FOO from repo A to repo B:

    repo B
     |
     |----module-FOO
     |----foo-1.0.rpm
     |----bar-0.7.rpm
     |----baz-1.0.rpm


Modules and their artifacts (RPMs), complicated case 2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| A Module lists artifacts it consists of.
| A Module can depend on other Modules.
| Complicated case 2 (RPM dependencies, module dependencies).

::

   dependencies: foo.rpm -> bar.rpm -> baz.rpm
                 module-FOO -> module-XXX
   module-FOO: [foo-1.0.rpm]
   module-XXX: [xxx-1.0.rpm, yyy-1.0.rpm]

   repo A
     |
     |----module-FOO
     |----module-XXX
     |----foo-1.0.rpm
     |----bar-1.0.rpm
     |----baz-1.0.rpm
     |----xxx-1.0.rpm
     |----yyy-1.0.rpm

   repo B
     |
     |----bar-0.7.rpm


| Use case #1: copy module and its artifacts
|              and module dependencies
|              and artifacts' *latest* dependencies
| Flag to use: ``recursive``

::

    Result of copying module-FOO from repo A to repo B:

    repo B
     |
     |----module-FOO
     |----module-XXX
     |----foo-1.0.rpm
     |----bar-0.7.rpm
     |----bar-1.0.rpm
     |----baz-1.0.rpm
     |----xxx-1.0.rpm
     |----yyy-1.0.rpm


| Use case #2: copy module and its artifacts
|              and module dependencies
|              and artifacts' *missing* dependencies
| Flag to use: ``recursive_conservative``

::

    Result of copying module-FOO from repo A to repo B:

    repo B
     |
     |----module-FOO
     |----module-XXX
     |----foo-1.0.rpm
     |----bar-0.7.rpm
     |----baz-1.0.rpm
     |----xxx-1.0.rpm
     |----yyy-1.0.rpm


.. Note::
   Irrespective of which flag is used and which RPMs are in a destination repo,
   **all** module artifacts are copied. ``recursive`` and ``recursive_conservative``
   process differently RPM-to-RPM dependencies only.
   Flags ``recursive`` and ``recursive_conservative`` can be used together,
   ``recursive_conservative`` takes precedence.


Erratum and related RPMs/Modules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| Erratum references RPMs and/or Modules.
| An Erratum lists RPMs which are suggested to be updated.
| In case a Module should be updated, an Erratum lists a Module and all its artifacts.

In case of a recursive copy in addition to the copy of Erratum itself, referenced RPMs
and Modules are copied as well similar to the rules and examples explained in previous sections.

Non-modular Errata and related RPMs, simple case
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
| A non-modular Erratum lists RPMs which are suggested to be updated.
| Simple case (no RPM dependencies).

::

   erratum-FOO: [foo-1.0.rpm]

   repo A
     |
     |----erratum-FOO
     |----foo-1.0.rpm


   repo B
     |
     |----foo-0.7.rpm



| Use case #1 (not recommended): copy erratum itself
| Flag to use: None

::

    Result of copying erratum-FOO from repo A to repo B:

    repo B
     |
     |----erratum-FOO
     |----foo-0.7.rpm

    Erratum is copied, while its related RPM is not!
    RPMs which are suggested for update are not in repo B!
    Copy this way when you know what you are doing and why.


| Use case #2: copy erratum and its related RPMs
| Flag to use: ``recursive`` or ``recursive_conservative``

::

    Result of copying erratum-FOO from repo A to repo B:

    repo B
     |
     |----erratum-FOO
     |----foo-1.0.rpm
     |----foo-0.7.rpm
     |----bar-0.7.rpm

    Older version ``foo-0.7.rpm`` remains in the repo B. 
    Using either ``recursive`` or ``recursive_conservative`` flag
    ``foo-1.0.rpm`` is copied to repo B as well since
    ``erratum-FOO`` refers to it.


Non-modular Errata and related RPMs, complicated case
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| A non-modular Erratum lists RPMs which are suggested to be updated.
| Complicated case (RPM dependencies).

::

   dependencies: foo.rpm -> bar.rpm -> bax.rpm-> baz.rpm
   erratum-FOO: [foo-1.0.rpm, bar-1.0.rpm]

   repo A
     |
     |----erratum-FOO
     |----foo-1.0.rpm
     |----bar-1.0.rpm
     |----bax-1.0.rpm
     |----baz-1.0.rpm


   repo B
     |
     |----foo-0.7.rpm
     |----bar-0.7.rpm
     |----bax-0.7.rpm



| Use case #1: copy erratum and related RPMs and RPMs' *latest* dependencies
| Flag to use: ``recursive``

::

    Result of copying erratum-FOO from repo A to repo B:

    repo B
     |
     |----erratum-FOO
     |----foo-1.0.rpm
     |----bar-1.0.rpm
     |----bax-1.0.rpm
     |----baz-1.0.rpm
     |----foo-0.7.rpm
     |----bar-0.7.rpm
     |----bax-0.7.rpm

| Use case #2: copy erratum and related RPMs and RPMs' *missing* dependencies
| Flag to use: ``recursive_conservative``

::

    Result of copying erratum-FOO from repo A to repo B:

    repo B
     |
     |----erratum-FOO
     |----foo-1.0.rpm
     |----bar-1.0.rpm
     |----baz-1.0.rpm
     |----foo-0.7.rpm
     |----bar-0.7.rpm
     |----bax-0.7.rpm

    RPMs which are referred in an erratum are always copied.
    ``foo-1.0.rpm``IS copied because it's referred in the erratum, even though ``foo-0.7.rpm``
    is present in repo B.
    ``bar.rpm`` is a dependency for ``foo.rpm``. ``bar-1.0.rpm`` IS copied because it's
    referred in the erratum, even though ``bar-0.7.rpm`` is present in repo B.
    ``bax.rpm`` is a dependency for ``bar.rpm``. ``bax-1.0.rpm`` is NOT copied because it's NOT
    referred in the erratum, and ``bax-0.7.rpm`` is present in repo B.
    ``baz.rpm`` is a dependency for ``bax.rpm``. ``baz-1.0.rpm`` IS copied because it's absent in
    repo B.


Modular Errata and related Modules/RPMs, simple case
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
| A modular Erratum lists a Module (which is suggested to be updated) and its artifacts.
| Simple case (no RPM dependencies, no modular dependencies).

::

   erratum-FOO: module-FOO
   module-FOO: [foo-1.0.rpm]

   repo A
     |
     |----erratum-FOO
     |----module-FOO
     |----foo-1.0.rpm


   repo B
     |
     |----foo-0.7.rpm


| Use case #1 (not recommended): copy erratum itself
| Flag to use: None

::

    Result of copying erratum-FOO from repo A to repo B:

    repo B
     |
     |----erratum-FOO
     |----foo-0.7.rpm

    Erratum is copied, while its related Modules is not!
    Module which is suggested for update is not in a repo B!
    Copy this way when you know what you are doing and why.


| Use case #2: copy erratum and its related Modules and Module's artifacts
| Flag to use: ``recursive`` or ``recursive_conservative``

::

    Result of copying erratum-FOO from repo A to repo B:

    repo B
     |
     |----erratum-FOO
     |----module-FOO
     |----foo-1.0.rpm
     |----foo-0.7.rpm


Modular Errata and related Modules/RPMs, complicated case 1
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| A modular Erratum lists a Module (which is suggested to be updated) and its artifacts.
| Complicated case 1 (RPM dependencies, no module dependencies).

::

   erratum-FOO: module-FOO
   module-FOO: [foo-1.0.rpm]
   dependencies: foo.rpm -> bar.rpm -> baz.rpm

   repo A
     |
     |----erratum-FOO
     |----module-FOO
     |----foo-1.0.rpm
     |----bar-1.0.rpm
     |----baz-1.0.rpm

   repo B
     |
     |----foo-0.7.rpm
     |----bar-0.7.rpm


| Use case #1: copy erratum and related module with its artifacts and artifacts' *latest* dependencies
| Flag to use: ``recursive``

::

    Result of copying module-FOO from repo A to repo B:

    repo B
     |
     |----erratum-FOO
     |----module-FOO
     |----foo-1.0.rpm
     |----bar-1.0.rpm
     |----baz-1.0.rpm
     |----foo-0.7.rpm
     |----bar-0.7.rpm

| Use case #2: copy erratum and related module with its artifacts and artifacts' *missing* dependencies
| Flag to use: ``recursive_conservative``

::

    Result of copying module-FOO from repo A to repo B:

    repo B
     |
     |----erratum-FOO
     |----module-FOO
     |----foo-1.0.rpm
     |----baz-1.0.rpm
     |----foo-0.7.rpm
     |----bar-0.7.rpm



Modular Errata and related Modules/RPMs, complicated case 2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

| A modular Erratum lists a Module (which is suggested to be updated) and its artifacts.
| A Module can depend on other Modules.
| Complicated case 2 (RPM dependencies, module dependencies).

::

   erratum-FOO: module-FOO
   module-FOO: [foo-1.0.rpm]
   module-XXX: [xxx-1.0.rpm, yyy-1.0.rpm]
   dependencies: foo.rpm -> bar.rpm -> baz.rpm
                 module-FOO -> module-XXX

   repo A
     |
     |----erratum-FOO
     |----module-FOO
     |----module-XXX
     |----foo-1.0.rpm
     |----bar-1.0.rpm
     |----baz-1.0.rpm
     |----xxx-1.0.rpm
     |----yyy-1.0.rpm

   repo B
     |
     |----foo-0.7.rpm
     |----bar-0.7.rpm


| Use case #1: copy erratum and module with its artifacts
|              and module dependencies
|              and artifacts' *latest* dependencies
| Flag to use: ``recursive``

::

    Result of copying module-FOO from repo A to repo B:

    repo B
     |
     |----erratum-FOO
     |----module-FOO
     |----module-XXX
     |----foo-1.0.rpm
     |----bar-1.0.rpm
     |----baz-1.0.rpm
     |----xxx-1.0.rpm
     |----yyy-1.0.rpm
     |----foo-0.7.rpm
     |----bar-0.7.rpm


| Use case #2: copy erratum and module with its artifacts
|              and module dependencies
|              and artifacts' *missing* dependencies
| Flag to use: ``recursive_conservative``

::

    Result of copying module-FOO from repo A to repo B:

    repo B
     |
     |----erratum-FOO
     |----module-FOO
     |----module-XXX
     |----foo-1.0.rpm
     |----baz-1.0.rpm
     |----xxx-1.0.rpm
     |----yyy-1.0.rpm
     |----foo-0.7.rpm
     |----bar-0.7.rpm


Protected Repositories
----------------------

Red Hat protects its repositories with SSL-based
entitlement certificates. Pulp supports both ends of that operation:

Each Pulp repository can be configured with a client entitlement certificate and
key that it will use to retrieve packages from a remote repository. This is only
required when the remote repository is protected, such as when connecting to the
Red Hat CDN.

Pulp can be supplied a CA certificate that it will use to verify the authenticity
of client certificates when clients try to access Pulp-hosted repositories. This
is only required when you want to protect a Pulp-hosted repository. Repositories
can have these protection settings specified individually, or they can be set
globally for all RPM-related repositories.

For each Pulp-hosted repository that is protected, a consumer certificate can be
supplied that will be distributed to consumers when they bind. That certificate
will allow them to access the protected repository.

Package Signatures and GPG Key ID Filtering
-------------------------------------------

RPM repositories have limited support for acting on package GPG signatures,
including requiring packages to have GPG signatures, and whitelisting signing
key IDs to only sync packages with matching signing key IDs. The signing key
ID filtering feature uses the 8-character "short" key ID, which does not uniquely
identify a GPG signing key. This feature does not verify package signatures.

This signature filtering is granted within the current importer settings and current
import of the content, without taking into consideration content already present in
the repository.

These features cannot be enable with on_demand or background download policies, since
access to the package files is required to get the GPG signature information.
Only the immediate download policy is compatible with signature filtering.

Export
------

In addition to publishing repositories as normal yum repositories over HTTP or
HTTPS, it is also possible to export repositories to ISO images, which are published
over HTTP or HTTPS, or to a directory on the Pulp server. Large repositories may be
split into several ISOs.

Proxy Settings
--------------

When retrieving packages from a remote repository, Pulp can use a proxy and can
supply basic authentication credentials to that proxy.

Bandwidth Throttling
--------------------

When downloading packages from a remote source, Pulp can limit the speed at which
data is transferred. The number of downloader threads can also be specified.

No Metalink Support
-------------------

Pulp RPM does not support any version of Metalink when syncing. Therefore for repositories that
publish Metalink data such as EPEL or Fedora RPM repositories, you cannot use the metalink url as
your feed url.

.. warning::

    Pulp is susceptible to a replay attack by either a malicious mirror or from a man-in-the-middle
    attack (MITM) when TLS is not used. When attacked, Pulp is presented older, legitimate packages.
    This forces Pulp to not receive package updates from either a malicious mirror or the non-TLS
    MITM. See `this blog post <https://patrick.uiterwijk.org/blog/2018/2/23/fedora-package-delivery-security>`_
    for more details about how Metalink would mitigate this.
