Quick Start
===========

Sync and Publish a Repo
-----------------------

The following command creates a new repository and sets its upstream feed URL to
that of the Pulp Project's own repository. When we later run a synchronize operation,
the contents of the remote repository will be downloaded and stored in our new
repository.

::

  $ pulp-admin rpm repo create --repo-id=zoo --relative-url=zoo \
  --feed=http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/zoo/
  Successfully created repository [pulp]

* ``--repo-id`` is required and must be unique.
* ``--relative-url`` is optional and was used here to make the path to the repository
  friendlier.
* ``--feed`` is only required if you want to sync content from an external yum
  repository, which in this case we do.

Now let's sync the repository, which downloads all of the packages from the remote
repository and stores them in our new repository.

::

  $ pulp-admin rpm repo sync run --repo-id=zoo
  +----------------------------------------------------------------------+
                       Synchronizing Repository [zoo]
  +----------------------------------------------------------------------+

  This command may be exited via ctrl+c without affecting the request.


  Downloading metadata...
  [\]
  ... completed

  Downloading repository content...
  [==================================================] 100%
  RPMs:       0/0 items
  Delta RPMs: 0/0 items

  ... completed

  Downloading distribution files...
  [==================================================] 100%
  Distributions: 0/0 items
  ... completed

  Importing errata...
  [-]
  ... completed

  Importing package groups/categories...
  [-]
  ... completed


  Task Succeeded



  Initializing repo metadata
  [-]
  ... completed

  Publishing Distribution files
  [-]
  ... completed

  Publishing RPMs
  [==================================================] 100%
  32 of 32 items
  ... completed

  Publishing Delta RPMs
  ... skipped

  Publishing Errata
  [==================================================] 100%
  4 of 4 items
  ... completed

  Publishing Comps file
  [==================================================] 100%
  3 of 3 items
  ... completed

  Publishing Metadata.
  [-]
  ... completed

  Closing repo metadata
  [-]
  ... completed

  Generating sqlite files
  ... skipped

  Publishing files to web
  [-]
  ... completed

  Writing Listings File
  [-]
  ... completed


  Task Succeeded


Your repository is now available to browse at
`https://localhost/pulp/repos/pulp_beta/ <https://localhost/pulp/repos/zoo/>`_.
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

  $ sudo pulp-consumer register --consumer-id=con1
  Enter password:
  Consumer [con1] successfully registered


Now we can proceed with binding to a specific repository. Binding causes the Pulp
repository to be setup on the consumer as a normal yum repository. Bound repositories
are added to the file ``/etc/yum.repos.d/pulp.repo``. Binding also allows the
server to initiate the installation of packages from that repository onto the
consumer. In this case, repository "zoo" has already been created on the Pulp
server and contains packages.

::

  $ pulp-consumer rpm bind --repo-id=zoo
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

  Install task created with id [ c89d4578-cb4e-451f-a87a-63272e77670e ]

  This command may be exited via ctrl+c without affecting the request.

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
