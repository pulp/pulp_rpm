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
* Group
* Category

Errata
------

.. probably deserves its own section, especially since there are extra consumer-side features
.. how to create package group, what are the requirements, what is the CSV, etc.
.. push count? what is that?

Protected Repositories
----------------------

`Red Hat <http://www.redhat.com>`_ protects its repositories with SSL-based
entitlement certificates. Pulp supports both ends of that operation:

Pulp can be given a client entitlement certificate and key that it will use to
retrieve packages from a remote repository. This is only required when the remote
repository is protected.

Pulp can be given a CA certificate that it will use to verify the authenticity
of client certificates when clients try to access Pulp-hosted repositories. This
is only required when you want to protect a Pulp-hosted repository. Repositories
can have these protection settings specified individually, or they can be set
globally for all RPM-related repositories.

ISO Export
----------

In addition to being published as a normal yum repository, it is also possible
to export a repository to ISOs. Large repositories will be spread across multiple
images as necessary.

Proxy Settings
--------------

When retrieving packages from a remote repository, Pulp can use a proxy and can
supply basic authentication credentials to that proxy.

Bandwidth Throttling
--------------------

When downloading packages from a remote source, Pulp can limit the speed at which
data is transferred. The number of downloader threads can also be specified.

