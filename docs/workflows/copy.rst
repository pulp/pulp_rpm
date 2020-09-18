Copy RPM content between repositories
=====================================

If you want to copy RPM content from one repository into another repository, you have two options
for doing so.


.. _basic-modify-workflow:

Basic Repository Modification API
---------------------------------

Like all Pulp repositories, you can use the ${repo_href}/modify/ endpoint to:

* add or remove individual content units from a repository by HREF
* roll back the content present in a repository to that of a previous version using 'base_version'
* clone a repository version using '"base_version". This operation will create a new repository
  version in the current repository which is a copy of the one specified as the "base_version",
  regardless of what content was previously present in the repository. This can be combined with
  adding and removing content units in the same call. For worklows check the :ref:`Recipes section <copy-recipes>`.

.. literalinclude:: ../_scripts/copy_basic.sh
   :language: bash


.. copy-workflow:

Advanced copy workflow
----------------------

.. note::

    The RPM copy API is a **tech preview**, while we hope it can remain stable, it may be subject
    to change in future releases.

RPM repositories have a large number of unique use cases for which the standard 'generic' Pulp
repository modification API is insufficient, so a separate RPM-specific API is provided for more
'advanced' use cases.

Several types of RPM content, such as Advisories (Errata), Package Groups, and Modules
depend on the existence of other content units to be "correct" or meaningful. For example:

#. An Advisory (Errata) references RPM Packages and Modules that are needed to address a
   particular bug or security concern. In order for the Advisory to be useful, these RPM packages
   or Modules should be present in the same repository - otherwise when a client tries to install
   them it will not be able to fully apply the Advisory fix.
#. A Package Group is a group of RPM packages. If the RPM packages that a Package Group contains
   are not present in the same repository, the Package Group is effectively "broken" and won't be
   possible to install correctly on a client system.
#. A Module can depend on other modules. If those modules are not present in the RPM repo, the
   module will not be installable on a client system.
#. RPM Packages typically depend on other RPM packages. If a lone RPM package is added to a
   repository without its dependencies, it will potentially not be installable on a client system.
#. A Module consists of many RPM packages (similar to a Package Group). If the module is added to
   a repository while the packages that its RPMs depend on are not, it may not be possible to
   install the module on a client system.

The advanced copy API exists primarily to address these use cases. Unlike the repository
modification API, when a copy is performed using the RPM copy API it is permitted to additionally
copy content in the background which you, the user, did not explicitly tell it to copy. For
example:

* When copying an Advisory (Errata) from one repository to another, all of the RPM packages
  directly referenced by the Advisory will also be copied. (note: this is best-effort, if the
  source repository doesn't contain some of the packages referenced, the copy will proceed
  without them).
* When copying RPM packages from one repository to another, all of the RPM packages that those
  packages depend on will also be copied.

The goal is to be as easy to use as possible while maintaining the "correctness" of the repository.

Dependency solving
__________________

When copying RPM packages between repositories, it is likely desirable to ensure that all of the
RPM dependencies they need to be "installable" on a client system are also present in the
repository they are being copied to. For example, if you want to add the "hexchat" RPM to a
new repository, and you want to be able to install it from that repository, the repository should
also contain its dependencies such as "libnotify" and "gtk3". This applies likewise to all RPM
concepts that "contain" RPMs also, such as Advisories (Errata), Modules, and PackageGroups. With
the RPM copy API, you are afforded the option to have all dependencies (and the dependencies of
those dependencies) copied for you automatically in the background, if they do not already exist
in the destination repository. In Pulp 2, this feature was called "recursive copy" because in a
sense it copies dependencies recursively.

Unfortunately, solving these complex dependency relationships can be quite expensive. For this
reason, the functionality to perform these checks is not enabled by default, and is instead
provided by setting the "dependency_solving" parameter to a value of True when making calls against
the API. Note that if you do elect to not perform dependency solving, it will be possible to
accidentally create incomplete repositories, if you are not careful.

.. note::

    While the default value for this "dependency_solving" parameter is currently "false", this
    default is potentially subject to change in the future - until such a time as this API is
    stabilized.

Dependency solving does have some restrictions to be aware of. The set of content contained by
all repositories used in a copy operation must be "dependency closed", which is to say that no
content in any repository may have a dependency which cannot be satisfied by any content present
in any of the other repositories involved in the copy operation.

For example, in CentOS 8, there are two primary repositories which are called "BaseOS" and
"AppStream". RPMs present in the "AppStream" repository frequently depend on RPMs which are
not present in "AppStream", but are present in "BaseOS", instead.

In order to copy RPMs from a Pulp-clone of the "AppStream" repository, you must perform a
"multi-repository copy" so that the dependencies can be properly resolved. Please see the
recipe section below for more details on how to do this.


.. _copy-recipes:

Recipes
_______

These are examples of how the RPM copy API should be used. This code isn't intended to be runnable
as-is, but rather as a template for how the calls should be constructed.

Create a new repository version in "dest_repo" containing all content units which are present in
the "source_repo_version". This essentially copies all content from the "source_repo_version" into
the "dest_repo", while leaving the content that was previously in the repository untouched, unless
retain package policy is set on the "dest_repo"

.. code-block:: sh

    POST /pulp/api/v3/rpm/copy/
    config:=[
        {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF"}
    ]

.. note::

   Retain package policy is set by `retain_package_versions` option.
   When set, it identifies the maximum number of versions of each package to keep; as new versions of
   packages are added by upload, sync, or copy, older versions of the same packages are automatically
   removed. A value of 0 means "unlimited" and will keep all versions of each package.

Create a new repository version in "dest_repo" containing the two "content" units specified by href,
which are present in the "source_repo_version".

.. code-block:: sh

    POST /pulp/api/v3/rpm/copy/
    config:=[
        {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF", "content": [$RPM_HREF1, $ADVISORY_HREF1]}
    ]
    dependency_solving=False

Create a new repository version in "dest_repo" containing the two "content" units specified by href,
which are present in the "source_repo_version". Instead of adding them to the content present in
the latest repository version present in "dest_repo", instead create a new version based upon
the version numbered "dest_base_version" in "dest_repo". These semantics are similar to how the
"base_version" parameter is used in the repository modification API.

.. code-block:: sh

    POST /pulp/api/v3/rpm/copy/
    config:=[
        {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF", "dest_base_version": "$DEST_BASE_VERSION", "content": [$RPM_HREF1, $ADVISORY_HREF1]}
    ]
    dependency_solving=False

Create a new repository version in "dest_repo" containing the two "content" units specified by href,
as well as all of their RPM and Module dependencies, which are present in the "source_repo_version".

.. code-block:: sh

    POST /pulp/api/v3/rpm/copy/
    config:=[
        {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF", "content": [$RPM_HREF1, $ADVISORY_HREF1]}
    ]
    dependency_solving=True

"Multi-repository-copy", required when any of the repositories involved in the copy are not "dependency closed".

Each of the pairs of source and destination repositories will see the content units that were
specified copied as normal. However when one of the content units has a dependency which is not
present in the same repository, but is present in one of the other "source" repositories listed,
it may be copied between the repos configured in that pair.

In the following example, if $RPM_HREF1 depends on a content unit which is only present in
$SRC_REPO_VERS_HREF2 and is not present in either $DEST_REPO_HREF or $DEST_REPO_HREF2, then
it will be copied from $SRC_REPO_VERS_HREF2 to $DEST_REPO_HREF2, even though no content was
specified to be copied between those repositories.

.. code-block:: sh

    POST /pulp/api/v3/rpm/copy/
    config:=[
        {"source_repo_version": "$SRC_REPO_VERS_HREF", "dest_repo": "$DEST_REPO_HREF", "content": [$RPM_HREF1, $ADVISORY_HREF1]},
        {"source_repo_version": "$SRC_REPO_VERS_HREF2", "dest_repo": "$DEST_REPO_HREF2", "content": []},
    ]
    dependency_solving=False
