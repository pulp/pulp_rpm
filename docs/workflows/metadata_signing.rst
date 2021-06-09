.. _metadata_signing:

Metadata Signing
================

The RPM plugin is able to sign repository metadata using a `signing service
<https://docs.pulpproject.org/workflows/signed-metadata.html>`_ configured by an administrator.
This enables package managers to verify the authenticity of metadata before installing packages
referenced by that metadata. The metadata signing is enabled for all repositories that have a
signing service associated with them.

Setup
-----

Let us assume that a signing service is already supplied by an administrator and is queryable via
REST API in an ordinary way. The only thing that needs to be done by a user is to create a new
repository with the associated signing service, like so:

.. literalinclude:: ../_scripts/repo_with_signing_service.sh
   :language: bash

Then, the repository needs to be published and a new distribution needs to be created out of it, as
usually. Follow the instructions provided :ref:`here<publication-workflow>` to do so.

The publication will automatically contain a detached ascii-armored signature and a public key.
Both, the detached signature and the public key, are used by package managers during the process of
verification.

Installing Packages
-------------------

When a distribution with signed repodata is created, a user can install packages from a signed
repository. But, at first, it is necessary to set up the configuration for the repository. One may
initialize the configuration by leveraging the utility ``dnf config-manager`` like shown below.
Afterwards, the user should be able to install the packages by running ``dnf install packages``.

.. literalinclude:: ../_scripts/install_from_signed_repository.sh
    :language: bash

.. note::

    Package managers take advantage of signed repositories only when the attribute ``repo_gpgcheck``
    is set to 1. Also, bear in mind that the attribute ``gpgkey`` should be configured as well to
    let the managers know which public key has to be used during the verification.
