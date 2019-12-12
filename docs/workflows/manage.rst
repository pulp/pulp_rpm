Manage Content
==============

Package
-------
Within a repository version there can be only one package (RPM or SRPM) with the same NEVRA.
NEVRA stands for name, epoch, version, release, architecture.

Advisory
--------


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


Comps.xml
---------
RPM plugin parses comps.xml metadata file into package groups, package environments, package
categories and langpacks.


Custom Repository Metadata
---------------------------

Custom or unknown repository metadata is considered any file listed in repomd.xml that Pulp does
not otherwise recognize. Within a repository version there can be only one custom repository
metadata of the same type.
