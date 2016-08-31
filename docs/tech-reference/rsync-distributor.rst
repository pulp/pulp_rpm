=====================
RPM rsync Distributor
=====================

Purpose:
========
The RPM rsync distributor publishes RPM content to a remote server. The distributor uses rsync over
ssh to perform the file transfer.

Configuration
=============
Pulp's SELinux policy includes a ``pulp_manage_rsync`` boolean. When enabled, the
``pulp_manage_rsync`` boolean allows Pulp to use rsync and make ssh connections. The boolean is
disabled by default. The RPM Rsync distributor will fail to publish with SELinux Enforcing unless
the boolean is enabled. To enable it, you can do this::

    $ sudo semanage boolean --modify --on pulp_manage_rsync

Here's an example of rpm_rsync_distributor configuration::

    {
        "distributor_id": "my_rpm_rsync_distributor",
        "distributor_type_id": "rpm_rsync_distributor",
        "distributor_config": {
            "remote": {
                "auth_type": "publickey",
                "ssh_user": "foo",
                "ssh_identity_file": "/home/user/.ssh/id_rsa",
                "host": "192.168.121.1",
                "root": "/home/foo/pulp_root_dir"
            },
            "predistributor_id": "yum_distributor"
        }
    }


``predistributor_id``
  The id of the yum_distributor associated with the same repository. The publish history of this
  yum_distributor determines if the publish will be incremental.

The ``distributor_config`` contains a ``remote`` section made up of the following settings:

``ssh_user``
  ssh user for remote server

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
  Absolute path to the remote root directory where all the data (content and published content)
  lives. Remote equivalent to ``/var/lib/pulp``. The repository's relative url is appended to the
  ``root`` to determine the location of published repository.

Optional configuration
----------------------

``force_full``
  If true, the rsync distributor will publish all of the content of the repository. If false
  (default), the publish is incremental when the predistributor's last publish was incremental.
  This value does not affect the ``skip_repodata`` and ``content_units_only`` configs.

``content_units_only``
  If true, the distributor will publish content units only (e.g. ``/var/lib/pulp/content``). The
  symlinks of a published repository will not be rsynced.

``skip_repodata``
  If true, repodata will be omitted from the publish.

``delete``
  If true, ``--delete`` is appended to the rsync command for symlinks and repodata so that any old files no longer present in
  the local published directory are removed from the remote server.

``remote_units_path``
  The relative path from the ``root`` where unit files should live. Defaults to ``content/units``.
