=====================
ISO rsync Distributor
=====================

Purpose:
========
The ISO rsync distributor publishes ISO content to a remote server. The distributor uses rsync over
ssh to perform the file transfer.

Configuration
=============
Here is an example iso_rsync_distributor configuration:

.. code-block:: json

    {
        "distributor_id": "my_iso_rsync_distributor",
        "distributor_type_id": "iso_rsync_distributor",
        "distributor_config": {
            "remote": {
                "auth_type": "publickey",
                "ssh_user": "foo",
                "ssh_identity_file": "/home/user/.ssh/id_rsa",
                "host": "192.168.121.1",
                "root": "/home/foo/pulp_root_dir"
            },
            "predistributor_id": "my_iso_distributor"
        }
    }


``predistributor_id``
  The id of the iso_distributor associated with the same repository. The PULP_MANIFEST published by
  the predistributor is copied to the remote server.

The ``distributor_config`` contains a ``remote`` section with the following settings:

``auth_type``
  Two authentication methods are supported: ``publickey`` and ``password``.

``ssh_user``
  The ssh user for remote server.

``ssh_identity_file``
  The path to the private key to be used as the ssh identity file. When ``auth_type`` is
  ``publickey`` this is a required config. The key has to be readable by user ``apache``.

``ssh_password``
  The password to be used for ``ssh_user`` on the remote server. ``ssh_password`` is required when
  ``auth_type`` is 'password'.

``host``
  The hostname of the remote server.

``root``
  The absolute path to the remote root directory where all the data (content and published content)
  lives. This is the remote equivalent to ``/var/lib/pulp``. The repo id is appended to the
  ``root`` path to determine the location of published repository.

Optional configuration
----------------------

``content_units_only``
  If true, the distributor will publish content units only (e.g. ``/var/lib/pulp/content``). The
  symlinks of a published repository will not be rsynced.

``delete``
  If true, ``--delete`` is appended to the rsync command for symlinks and repodata so that any old
  files no longer present in the local published directory are removed from the remote server.

``remote_units_path``
  The relative path from the ``root`` where unit files will live. Defaults to ``content/units``.
