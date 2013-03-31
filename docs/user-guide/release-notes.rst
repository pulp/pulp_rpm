=============
Release Notes
=============

Pulp 2.1.0
==========

New Features
------------

#. Pulp 2.1 now supports Fedora 18 and Apache 2.4.
#. There is now limited ISO repository support that is accessible through the API. We have not yet released
   extensions for our admin client to make use of ISO features, and not all intended API features are
   implemented yet.

Notes of Caution
----------------

#. The pulp-consumer bind and unbind operations have been moved out of the Pulp project into this project.
   These operations can now be found under pulp-consumer rpm {bind,unbind}.
#. The "pulp-admin rpm consumer [list, search, update, unregister, history]" commands from this project have
   been moved into the Pulp project, and can now be found under "pulp-admin consumer \*".
#. The export distributor now published to a different absolute path than it did in Pulp 2.0. Previously, the
   exported ISOs were published on the Pulp server under ``/pulp/isos/``. They will now be published under
   ``/pulp/exports/``. It is the user's responsibility to move any ISOs they have exported out of
   ``/pulp/isos/`` before upgrading. This will be covered in the :ref:`upgrade_instructions`.

.. _upgrade_instructions:

Upgrade Instructions
--------------------

Migrate Exported ISOs
^^^^^^^^^^^^^^^^^^^^^

Before upgrading, we will need to migrate any exported ISOs that were created using the export distrubutor to
their new location for Pulp 2.1. These ISOs can be in two different places in your filesystem, depending on
whether they were published over HTTP or HTTPS, or both. The HTTP published ISOs will be found in
``/var/lib/pulp/published/http/isos/``. If there are any files or folders in that location, you can move them to
their new location, or remove them if you do not need them anymore. This command will move them::

    $ sudo mv /var/lib/pulp/published/http/isos /var/lib/pulp/published/http/exports

Similarly, ISOs published over HTTPS will be found in ``/var/lib/pulp/published/https/isos/``. If you do not
wish to remove them, you can move them with this command::

    $ sudo mv /var/lib/pulp/published/https/isos /var/lib/pulp/published/https/exports

Upgrade the Pulp Packages
^^^^^^^^^^^^^^^^^^^^^^^^^

To upgrade to the new Pulp release, you should begin by using yum to install the latest RPMs from the Pulp
repository, run the database migrations, and cleanup orphaned packages::

    $ sudo yum upgrade
    $ sudo pulp-manage-db
    $ sudo pulp-admin orphan remove --all
