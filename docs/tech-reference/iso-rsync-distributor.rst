=====================
ISO rsync Distributor
=====================

Purpose:
========
The ISO rsync distributor publishes ISO content to a remote server. The distributor uses rsync over
ssh to perform the file transfer.

Configuration
=============
Pulp's SELinux policy includes a ``pulp_manage_rsync`` boolean. When enabled, the
``pulp_manage_rsync`` boolean allows Pulp to use rsync and make ssh connections. The boolean is
disabled by default. The ISO Rsync distributor will fail to publish with SELinux Enforcing unless
the boolean is enabled. To enable it, you can do this::

    $ sudo semanage boolean --modify --on pulp_manage_rsync

Here is an example iso_rsync_distributor configuration::

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

``ssh_user``
  The ssh user for remote server.

``ssh_identity_file``
  Absolute path to the private key that will be used as identity file for ssh. The key must be
  owned by user ``apache`` and must not be readable by other users. If the POSIX are too loose,
  the SSH application will refuse to use the key. Additionally, if SELinux is Enforcing, Pulp
  requires the key to be labeled with the ``httpd_sys_content_t`` SELinux context. This can be
  applied to the file with::

    $ sudo chcon -t httpd_sys_content_t  /path/to/ssh_identity_file

``host``
  The hostname of the remote server.

``root``
  The absolute path to the remote root directory where all the data (content and published content)
  lives. This is the remote equivalent to ``/var/lib/pulp``. The ``relative_url`` of the
  predistributor is appended to the ``root`` to determine the location of published repository.

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

``rsync_extra_args``
  list of strings that can be used to extend default arguments used for rsync call.
