Manage Content
==============

Package
-------

Within a repository version there can be only one package (RPM or SRPM) with the same NEVRA.
NEVRA stands for name, epoch, version, release, architecture.

Repositories can be set to only allow packages signed by specific key(s) to be added to them by setting the `allowed_pub_keys` field on the repo.
That field is a list of Key IDs for the acceptable signing keys.
A Key ID is the last 16 digits of the hex fingerprint of the public keys (import the key to gpg, do `gpg --list-keys`, take the last 16 digits).
For example, a repo that had set `allowed_pub_keys: ["ABCDEF0123456789", "0987654321FEDCBA"]` would only allow packages signed by those two keys to be added, and any update that contained an RPM *not* signed by one of them would fail.


Advisory
--------

.. warning::
    Advisory Upload is provided as a tech preview in Pulp RPM 3.0. Functionality may not fully work and backwards compatibility when upgrading to future Pulp RPM releases is not guaranteed.

Advisory is sometimes referred as an Erratum.
It carries information about the updates: which packages need to be updated to solve a specific problem.

There can be only one advisory with the same id in a repository version.

If advisory with the same id already exists in a repository version at the time when another one is being added,
or if a remote repository holds duplicate advisory-ids at sync time, a conflict resolution mechanism is applied.
As a result, a new combined advisory might be created and added to a repository instead of two conflicting ones.
It's also possible that one of advisories will be kept as is, in case it's a newer version of the other.
For more information of the conflict resolution logic, see `this detailed explanation <https://github.com/pulp/pulp_rpm/blob/1d507db453d4e6a91518beb4981a434a29cc3c01/pulp_rpm/app/advisory.py#L81-L96>`__.


Modularity Metadata
-------------------

RPM plugin parses a modules.yaml metadata file into modules and their defaults.

Modulemd is uniquely identified by NSVCA which stands for name, stream, version, context, and
architecture. Modulemd contains artifacts (RPM packages), whenever a modulemd is being added or
copied to a repository, modulemd's packages are carried over. In case a modulemd is removed from
a repository version, modulemd's packages are removed as well, this way repository version will
not contain ursine (modulemd unreferenced) packages and modulemd consistency will be preserved.

Within a repository version there can be only one modulemd-defaults with the same modulemd name.


Distribution Tree
-----------------

.. warning::
    Support for Distribution Trees is provided as a tech preview in Pulp RPM 3.0. Functionality may not fully work and backwards compatibility when upgrading to future Pulp RPM releases is not guaranteed.

Distribution is sometimes referred as a kickstart tree.
A tree is architecture-specific and is made up of:

 * One or more RPM repositories
 * Bootable ISO images
 * PXE boot images including EFI boot files, ISOLINUX boot files, and one or more kernel images with initial RAM disks.

Almost all the content in a tree is described in a metadata file called the treeinfo file (sometimes .treeinfo).

There can be only one Distribution Tree in a repository verison.


Comps.xml
---------

RPM plugin parses comps.xml metadata file into package groups, package environments, package
categories and langpacks.


Custom Repository Metadata
---------------------------

Custom or unknown repository metadata is considered any file listed in repomd.xml that Pulp does
not otherwise recognize. Within a repository version there can be only one custom repository
metadata of the same type.

