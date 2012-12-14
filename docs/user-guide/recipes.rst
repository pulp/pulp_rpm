.. _recipes:

Recipes
=======


Mirror a Remote Repository
--------------------------

This is an example of creating a local mirror of a remote repository. In this
case, we will mirror the `Foreman <http://theforeman.org/>`_ repository.

::

  $ pulp-admin rpm repo create --repo-id=foreman --feed=http://yum.theforeman.org/rc/el6/i386/ --relative-url=foreman
  Successfully created repository [foreman]

  $ pulp-admin rpm repo sync run --repo-id=foreman
  +----------------------------------------------------------------------+
                     Synchronizing Repository [foreman]
  +----------------------------------------------------------------------+

  This command may be exited by pressing ctrl+c without affecting the actual
  operation on the server.

  Downloading metadata...
  [|]
  ... completed

  Downloading repository content...
  [==================================================] 100%
  RPMs:       87/87 items
  Delta RPMs: 0/0 items
  Tree Files: 0/0 items
  Files:      0/0 items
  ... completed

  Importing errata...
  [\]
  ... completed

  Importing package groups/categories...
  [-]
  ... completed

  Publishing packages...
  [==================================================] 100%
  Packages: 87/87 items
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

A local copy of the repository is now available at
`https://localhost/pulp/repos/foreman/ <https://localhost/pulp/repos/foreman/>`_.
(adjust the hostname as necessary)

To keep the repository current, it might be desireable to synchronize it on a
regular schedule. The following command sets a schedule of synchronizing once
a day.

::

  $ pulp-admin rpm repo sync schedules create -s '2012-12-15T00:00Z/P1D' --repo-id=foreman
  Schedule successfully created


Use a Proxy
-----------

Using a web proxy is fairly straight-forward. Proxy details are specified when
creating the repository, as in this example:

::

  $ pulp-admin rpm repo create --repo-id=foo --proxy-url=http://bar.net \
  --proxy-port=1234 --proxy-user=me --proxy-pass=letmein \
  --feed=http://bar.net/repos/foo/
  Successfully created repository [foo]

.. warning::
  The password is stored in clear text and may be presented in clear text by the
  command line utility. Do not use sensitive credentials for your web proxy.


Sync a Protected Repo
---------------------

Syncing against a protected repository requires specifying some SSL certificates.
The ``pulp-admin rpm repo create`` command does a good job of documenting these
options, but the below example may help pull it all together.

This example was run on a RHEL6 server with an active subscription.

Note that you will need to adjust the file names for the certificate and key in
``/etc/pki/`` to match your own. Also note that this needs to run as root to
have permission to read the certificates and key.

::

  $ sudo pulp-admin rpm repo create --repo-id=rhel-6-server \
  --feed=https://cdn.redhat.com/content/dist/rhel/server/6/6Server/x86_64/os \
  --feed-ca-cert=/etc/rhsm/ca/redhat-uep.pem --feed-cert=/etc/pki/entitlement/8435737662014631983.pem \
  --feed-key=/etc/pki/entitlement/8435737662014631983-key.pem
  Successfully created repository [rhel6server]

  $ pulp-admin rpm repo sync run --repo-id=rhel6server
  +----------------------------------------------------------------------+
                   Synchronizing Repository [rhel6server]
  +----------------------------------------------------------------------+

  This command may be exited by pressing ctrl+c without affecting the actual
  operation on the server.

  Downloading metadata...
  [/]
  ... completed

  Downloading repository content...
  [                                                  ] 1%
  RPMs:       91/8769 items
  Delta RPMs: 0/0 items
  Tree Files: 0/7 items
  Files:      0/0 items


Publish a Protected Repo
------------------------

.. rbarlow will write this as part of https://bugzilla.redhat.com/show_bug.cgi?id=887032

Publish ISOs
------------

Given a repository "foo" that contains packages, it is possible to publish all
of its packages as ISO images. There are extra command line options that can
limit which packages are selected; it's left as an exercise for the reader to
consult the help text of the ``export run`` command.

If the total size is less than 630MB, Pulp will create one CD-sized ISO image.
If it is greater, Pulp will create as many DVD-sized ISO images (4308MB) as
required to fit the selected packages.

::

  $ pulp-admin rpm repo export run --repo-id=foo
  +----------------------------------------------------------------------+
                        Publishing Repository [foo]
  +----------------------------------------------------------------------+

  This command may be exited by pressing ctrl+c without affecting the actual
  operation on the server.

The resulting ISOs are now available at `https://localhost/pulp/isos/pulp/
<https://localhost/pulp/isos/pulp/>`_ (adjust hostname as necessary)
