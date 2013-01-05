Quick Start
===========

Sync and Publish a Repo
-----------------------

The following command creates a new repository and sets its upstream feed URL to
that of the Pulp Project's own repository. When we later run a synchronize operation,
the contents of the remote repository will be downloaded and stored in our new
repository.

::

  $ pulp-admin rpm repo create --repo-id=pulp --relative-url=pulp_beta \
  --feed=http://repos.fedorapeople.org/repos/pulp/pulp/v2/beta/fedora-17/x86_64/
  Successfully created repository [pulp]

* ``--repo-id`` is required and must be unique.
* ``--relative-url`` is optional and was used here to make the path to the repository
  friendlier.
* ``--feed`` is only required if you want to sync content from an external yum
  repository, which in this case we do.

Now let's sync the repository, which downloads all of the packages from the remote
repository and stores them in our new repository.

::

  $ pulp-admin rpm repo sync run --repo-id=pulp
  +----------------------------------------------------------------------+
                      Synchronizing Repository [pulp]
  +----------------------------------------------------------------------+

  This command may be exited by pressing ctrl+c without affecting the actual
  operation on the server.

  Downloading metadata...
  [/]
  ... completed

  Downloading repository content...
  [==================================================] 100%
  RPMs:       36/36 items
  Delta RPMs: 0/0 items
  Tree Files: 0/0 items
  Files:      0/0 items
  ... completed

  Importing errata...
  [-]
  ... completed

  Importing package groups/categories...
  [-]
  ... completed

  Publishing packages...
  [==================================================] 100%
  Packages: 36/36 items
  ... completed

  Publishing distributions...
  [==================================================] 100%
  Distributions: 0/0 items
  ... completed

  Generating metadata
  [/]
  ... completed

  Publishing repository over HTTPS
  [-]
  ... completed

Your repository is now available to browse at
`https://localhost/pulp/repos/pulp_beta/ <https://localhost/pulp/repos/pulp_beta/>`_.
(adjust the hostname as necessary)

Consumer Setup and Use
----------------------

On a Pulp consumer, once you have completed the installation process, the next
step is to register with the Pulp server. This allows the server to track what
is installed on the consumer and initiate actions on the consumer, such as package
install and system reboot.

.. note::
  You must use login credentials for this command. Also note that this command must be run with root privileges.

::

  $ sudo pulp-consumer -u admin register --consumer-id=con1
  Enter password:
  Consumer [con1] successfully registered


Now we can proceed with binding to a specific repository. Binding causes the Pulp
repository to be setup on the consumer as a normal yum repository. Bound repositories
are added to the file ``/etc/yum.repos.d/pulp.repo``. Binding also allows the
server to initiate the installation of packages from that repository onto the
consumer. In this case, repository "zoo" has already been created on the Pulp
server and contains packages.

::

  $ pulp-consumer bind --repo-id=zoo
  Bind tasks successfully created:

  Task Id: 44d64951-857a-4985-bfd9-dd6ead841065

  Task Id: 14782cfa-bdb7-4307-b2b1-f1a0b4331d66


.. note::
  The binding request is asynchronous and does not complete until the server has
  responded with binding information. This is why you see task IDs in the output
  above. That said, it happens very quickly and will almost certainly be done
  before you can type your next command.

At this point, the consumer is ready to install packages from the "zoo" repository.
Let's initiate a package install from the server.

::

  $ pulp-admin rpm consumer package install run --consumer-id=con1 -n wolf
  Install task created with id [0ad6f101-3abc-43c4-b103-04719239e5ae]

  This command may be exited via ctrl+c without affecting the install.

  Refresh Repository Metadata             [ OK ]
  Downloading Packages                    [ OK ]
  Check Package Signatures                [ OK ]
  Running Test Transaction                [ OK ]
  Running Transaction                     [ OK ]
  Install Succeeded

  +----------------------------------------------------------------------+
                                 Installed
  +----------------------------------------------------------------------+

  Name:    wolf
  Version: 9.4
  Arch:    noarch
  Repoid:  zoo

Now the package "wolf" is installed on the consumer, and you can verify this by
running ``yum info wolf`` on the consumer.


Next Steps
----------

This guide documents features and concepts that are specific to RPM support. The
Pulp User Guide has much more information about how to perform common operations
like search repositories, copy packages from one repository to another, etc.

Please check out the :ref:`recipes` section for more advanced use cases.
