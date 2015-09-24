.. _recipes:

*******
Recipes
*******

Mirror a Remote Repository
==========================

This is an example of creating a local mirror of a remote repository. In this
case, we will mirror the `Foreman <http://theforeman.org/>`_ repository.

::

  $ pulp-admin rpm repo create --repo-id=foreman --feed=http://yum.theforeman.org/releases/1.1/el6/x86_64/ --relative-url=foreman
  Successfully created repository [foreman]

* ``--repo-id`` is required and must be unique.
* ``--relative-url`` is optional and was used here to make the path to the repository
  friendlier.
* ``--feed`` is only required if you want to sync content from an external yum
  repository, which in this case we do.

::

  $ pulp-admin rpm repo sync run --repo-id=foreman
  +----------------------------------------------------------------------+
                   Synchronizing Repository [foreman]
  +----------------------------------------------------------------------+

  This command may be exited by pressing ctrl+c without affecting the actual
  operation on the server.

  Downloading metadata...
  [/]
  ... completed

  Downloading repository content...
  [==================================================] 100%
  RPMs:       98/98 items
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

  Publishing packages...
  [==================================================] 100%
  Packages: 98/98 items
  ... completed

  Publishing distributions...
  [==================================================] 100%
  Distributions: 0/0 items
  ... completed

  Generating metadata
  [\]
  ... completed

  Publishing repository over HTTPS
  [\]
  ... completed

The full URL to a published repository is derived from the following information:
 * The server name of the Pulp server. This should be the same hostname used in the
   CN of the server's SSL certificate, otherwise SSL verification on the client
   will likely fail. The configuration of that certificate is handled by Apache,
   typically in the ``ssl.conf`` configuration file.
 * The Apache alias at which Pulp RPM repositories are hosted. This value is set
   in the ``pulp_rpm.conf`` file located in Apache's ``conf.d`` directory. By
   default, this is set to ``/pulp/repos``.
 * The relative URL of the repository being published. This can be explicitly set
   when the repository is created in Pulp. If it is not explicitly set, Pulp will
   derive this value using the relative URL of the repository's feed. For feedless
   repositories, the repository ID is used.

Applying these rules to the above example repository, the published repository
can be found (adjusting the hostname as necessary) at:
`https://localhost/pulp/repos/foreman/ <https://localhost/pulp/repos/foreman/>`_.

Had the relative URL not been explicitly set in the repository, the hosted URL
would be:
``https://localhost/pulp/repos/releases/1.1/el6/x86_64/``.

To keep the repository current, it might be desirable to synchronize it on a
regular schedule. The following command sets a schedule of synchronizing once
a day.

::

  $ pulp-admin rpm repo sync schedules create -s '2012-12-15T00:00Z/P1D' --repo-id=foreman
  Schedule successfully created


.. _configure-proxy:

Use a Proxy
===========

Using a web proxy is fairly straight-forward. Proxy details are specified when
creating the repository, as in this example:

::

  $ pulp-admin rpm repo create --repo-id=foo --proxy-host=http://bar.net \
  --proxy-port=1234 --proxy-user=me --proxy-pass=letmein \
  --feed=http://bar.net/repos/foo/
  Successfully created repository [foo]

.. warning::
  The password is stored in clear text and may be presented in clear text by the
  command line utility. Do not use sensitive credentials for your web proxy.

Alternatively, Pulp can be configured to use a specific proxy for all yum
repositories by adding the following settings to
``/etc/pulp/server/plugins.conf.d/yum_importer.json``

::

  {
   "proxy_host" : "<url>",
   "proxy_port" : <port>,
   "proxy_username" : "<username>",
   "proxy_password" : "<password>"
  }

.. note:: This is a JSON file, so care must be taken when editing it.


Sync a Protected Repo
=====================

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

If you would prefer not to use the entitlement certificates from an existing
RHEL installation, you can also acquire the entitlement certificate, key, and
`CA certificate <https://access.redhat.com/management/ca_cert/download>`_ using
the Red Hat Customer Portal. To retrieve the entitlement certificate and key,
you will need to view your
`Registered Consumers <https://access.redhat.com/management/consumers/>`_. On
that page, there is a "Systems" tab, and in that tab there is a link to
`Register a system <https://access.redhat.com/management/consumer/consumers/create/system>`_.
Fill out the form with the relevant details for your Pulp Server, and click
"Register". Once you have registered your system, you must now attach a
subscription to it with the "Attach a subscription" link on the page for the
newly registered system. In the pop up, select the subscriptions that you want
to apply to the Pulp Server and click "Attach selected". You will now see the
selected subscriptions in the "Attached Subscriptions" table, and you can use
the "Download" link from the "Entitlement Certificate" column to retrieve the
certificate and key, bundled into a single file. You can pass that same file as
the ``--feed-cert`` and ``--feed-key`` options when you create the repo.

It is also possible to sync a repo that is protected via basic authentication.
The ``--basicauth-user`` and ``--basicauth-pass`` options are used for this
during repo creation or update.

.. _export-repos:

Export Repositories and Repository Groups
=========================================

If you have a Pulp server that does not have access to the Internet, it is possible
to use a second Pulp server, which does have Internet access, to retrieve repositories and
repository updates for your disconnected server. The full list of options can be seen by
running ``pulp-admin rpm repo export run --help``.

The general workflow is as follows:

1. Use the connected Pulp server to sync one or more repositories.
2. Export these repositories to ISOs: ``pulp-admin rpm repo export run --repo-id=demo-repo``

::

  $ pulp-admin rpm repo export run --repo-id=demo-repo
  +----------------------------------------------------------------------+
                        Publishing Repository [demo-repo]
  +----------------------------------------------------------------------+

  This command may be exited by pressing ctrl+c without affecting the actual
  operation on the server.

Which, if publishing over HTTP, could be found at
`http://localhost/pulp/exports/repo/demo-repo/ <http://localhost/pulp/exports/repo/demo-repo/>`_
(adjust hostname and repo-id as necessary.)

3. Transport the ISOs to the disconnected Pulp server
4. Mount each ISO and copy its contents to a directory on the disconnected Pulp server

::

  $ cp -r /path/to/mounted/iso1/ /path/to/extracted/content
  $ cp -r /path/to/mounted/iso2/ /path/to/extracted/content

5. On the disconnected Pulp server, create a new repository with the feed pointing at
   the directory containing the ISO contents:
   ``pulp-admin rpm repo create --repo-id=demo-repo --feed=file:///path/to/extracted/content/``
6. Sync the repository using ``pulp-admin rpm repo sync run --repo-id=demo-repo``

The workflow for exporting repository groups is quite similar. The command is
``pulp-admin rpm repo group export run``. Repository groups can contain any content type,
but this command will only export the yum repositories.

It is also possible to export all rpms and errata associated with a repository in a given
time frame using the ``--start-date`` and ``--end-date`` options. This is helpful if you have
already exported the repository and would like to only export updates. Be aware that since this
does not export package groups or categories, any updates to these will not be reflected on the
disconnected Pulp server. There is currently no support in the pulp-admin command-line utility
for uploading these incremental updates back into Pulp; you must use the REST API for these uploads.

.. warning::
  It is very important keep track of the last time you performed an incremental export.
  If you fail use the correct date range, some dependencies may be missing from the export.
  It is recommended that you overlap the date ranges to be safe.

The default behavior is to create a set of ISO images and publish them over
HTTP or HTTPS to ``/pulp/exports/repo/<repo-id>/``, or if publishing a repo
group, ``/pulp/exports/repo_group/<group-id>/``. The default image size will
fit on a DVD (4308MB). However, if you would prefer to use an external hard drive
to transport the repositories, you can use the ``--export-dir`` option, which will
export the repository to a directory on the Pulp server rather than creating a set
of ISOs and publishing them over HTTP or HTTPS. If you choose this option, simply
skip step 4.


Errata
======

.. _search-errata:

Searching for Errata
--------------------

Pulp has a very powerful search interface that can be used to search content
units. In this recipe, you will learn how to use it to search for errata that
have been issued on or after a date, and also how to search for errata by type.
Let's start by defining a repo cleverly called ``repo`` with a demo feed::

    $ pulp-admin rpm repo create --repo-id=repo \
      --feed=http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/pulp_unittest/ \
      --relative-url=repo
    Successfully created repository [repo]

Now let's sync the repo so it has some errata for us to search::

    $ pulp-admin rpm repo sync run --repo-id=repo

The contents of our example repository are from a few years ago, but it includes
errata over a span of a few years. Suppose that I wanted to know which errata
were issued on or after December 1, 2009. For this example, I will include the
``--fields=id`` flag to limit the output to just be the IDs of the errata, but
you can season that flag to taste, or omit it if you want to see everything::

    $ pulp-admin rpm repo content errata --filters='{"issued": {"$gte": "2009-12-01"}}' \
      --repo-id=repo --fields=id
    Id: RHBA-2010:0010

    Id: RHBA-2010:0205

    Id: RHBA-2010:0206

    Id: RHBA-2010:0222

    Id: RHBA-2010:0251

    Id: RHBA-2010:0281

    Id: RHBA-2010:0282

    Id: RHBA-2010:0294

    Id: RHBA-2010:0418

We already talked about the ``--fields=id`` flag, so let's focus on the
``--filters='{"issued": {"$gte": "2009-12-01"}}'`` flag. :command:`pulp-admin`
has some built in simple filtering capabilities, but they aren't as powerful as
the filtering we can achieve with the ``--filters`` flag. We can use this flag
to pass a `JSON filter <http://docs.mongodb.org/manual/reference/operators/>`_
to MongoDB to have it apply any arbitrary filter we want. In our case, we want
to look for the "issued" field of our errata being greater than or equal to
2009-12-01.

There are three different types of errata: Security Advisories (RHSAs), Bug Fix
Advisories (RHBAs), and Product Enhancement Advisories (RHEAs). Suppose we
wanted to know which RHSAs were available in a repo. We would run this command::

    $ pulp-admin rpm repo content errata --match type=security \
      --repo-id=repo --fields=id
    Id: RHSA-2007:0114

    Id: RHSA-2007:0323

    Id: RHSA-2008:0194

    Id: RHSA-2008:0892

    Id: RHSA-2009:0003

    Id: RHSA-2009:0382

    Id: RHSA-2009:1472

For this command we asked Pulp to find errata that had their type field set to
"security". We can also find these by applying a regex to the id field::

    $ pulp-admin rpm repo content errata \
      --match id=^RHSA --repo-id=repo

In this example, we asked MongoDB to look for errata that had an ``id`` that
matched our supplied
`Regular Expression <http://docs.mongodb.org/manual/reference/operators/#_S_regex>`_.
The carat at the start of our regular expression will match the beginning of the
``id`` field, and we used RHSA after that to make sure the ID was an RHSA and
not an RHBA or RHEA.

.. _copy-errata-recipe:

Copy Errata From One Repository to Another
------------------------------------------

The :command:`pulp-admin` utility can be used to copy errata from one repository to
another. In this recipe, we will create two repositories, sync one with a
sample upstream repository, and then copy an erratum from it to the other.
Let's begin by creating our two repositories, ``repo_1`` and ``repo_2``::

    $ pulp-admin rpm repo create --repo-id=repo_1 \
      --feed=http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/pulp_unittest/ \
      --relative-url=repo_1
    Successfully created repository [repo_1]

    $ pulp-admin rpm repo create --repo-id=repo_2 \
      --relative-url=repo_2
    Successfully created repository [repo_2]
    
Next, we will sync ``repo_1``, so that it will have some errata that we can
copy::

    $ pulp-admin rpm repo sync run --repo-id=repo_1
    +----------------------------------------------------------------------+
    Synchronizing Repository [repo_1]
    +----------------------------------------------------------------------+

    This command may be exited by pressing ctrl+c without affecting the actual
    operation on the server.

    Downloading metadata...
    [|]
    ... completed

    Downloading repository content...
    [==================================================] 100%
    RPMs:       3/3 items
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

    Publishing packages...
    [==================================================] 100%
    Packages: 3/3 items
    ... completed

    Publishing distributions...
    [==================================================] 100%
    Distributions: 3/3 items
    ... completed

    Generating metadata
    [/]
    ... completed

    Publishing repository over HTTPS
    [-]
    ... completed

    Publishing repository over HTTP
    [-]
    ... skipped

Now ``repo_1`` has errata and other units, and ``repo_2`` has no units at all.
Suppose that we would like to pull all of the security updates from ``repo_1``
to ``repo_2``. We can determine which errata are RHSA by using a match filter::

    $ pulp-admin rpm repo content errata --match type=security \
      --repo-id=repo_1 --fields=id
    Id: RHSA-2007:0114

    Id: RHSA-2007:0323

    Id: RHSA-2008:0194

    Id: RHSA-2008:0892

    Id: RHSA-2009:0003

    Id: RHSA-2009:0382

    Id: RHSA-2009:1472

Running that same command for ``repo_2`` doesn't show any errata, so let's use
the unit copy command to bring these RHSAs over, but not the RHBAs or the
RHEAs::

    $ pulp-admin rpm repo copy errata --match type=security \
      --from-repo-id=repo_1 --to-repo-id=repo_2
    Progress on this task can be viewed using the commands under "repo tasks".

.. note::
  Use the --recursive flag to copy any dependencies of units being copied from the source repo
  into the destination repo.

We can inspect the progress of this operation using
``pulp-admin repo tasks list --repo-id=repo_1``. There are only a few
errata to be copied here so it should be complete shortly. Now we can inspect
the contents of ``repo_2``::

    $ pulp-admin rpm repo content errata --repo-id=repo_2 --fields=id
    Id: RHSA-2007:0114

    Id: RHSA-2007:0323

    Id: RHSA-2008:0194

    Id: RHSA-2008:0892

    Id: RHSA-2009:0003

    Id: RHSA-2009:0382

    Id: RHSA-2009:1472

.. _create-errata-recipe:

Create Your Own Errata
----------------------

You can also create your own errata on a repo using the Pulp client. In order to
do this, you will need to create a few
`CSV <http://en.wikipedia.org/wiki/Comma-separated_values>`_ files and provide a
few data fields to the :command:`pulp-admin` client.

Let's begin by making a repo and syncing it::

    $ pulp-admin rpm repo create --repo-id=repo \
      --feed=http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/pulp_unittest/
    Successfully created repository [repo]

    $ pulp-admin rpm repo sync run --repo-id=repo

Now let's create a new errata that references one of the test packages from this
repo called pulp-test-package. The first file that we will need to provide is a
references CSV file. This CSV should have four columns: href, type, id, and
description, giving a link to the referenced bug report or CVE, the type of the
reference, the ID of the reference, and a brief description. Here is an example,
named references.csv, wherein you can see that pulp-test-package-0.2.1 has some
serious issues::

    http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=123456,bugzilla,123456,pulp-test-package-0.2.1 prints mean error messages to users
    http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=654321,bugzilla,654321,pulp-test-package-0.2.1 causes users' machines to run out of bits/bytes/whatever. The users must wait until the next supply comes next week

Next, we will need to provide a list of packages that the errata applies to.
This CSV provides a list of packages that address the issue that the errata
tracks with the following columns: name, version, release, epoch, arch,
filename, checksum, checksum_type, and src. For example, let's create
package_list.csv for this::

    pulp-test-package,0.3.1,1.fc11,0,x86_64,pulp-test-package-0.3.1-1.fc11.x86_64.rpm,6bce3f26e1fc0fc52ac996f39c0d0e14fc26fb8077081d5b4dbfb6431b08aa9f,sha256,pulp-test-package-0.3.1-1.fc11.src.rpm

Now that we have these two files, we can create our new errata like so::

    $ pulp-admin rpm repo uploads erratum --erratum_id=DEMO_ID_1 \
      --title="1: pulp-test-package bit conservation" \
      --description="1: pulp-test-package now conserves your precious bits." \
      --version=1 --release="el6" --type="bugzilla" --status="final" \
      --updated="`date`" --issued="`date`" --reference-csv=references.csv \
      --pkglist-csv=package_list.csv --from=pulp-list@redhat.com --repo-id=repo
    +----------------------------------------------------------------------+
                                  Unit Upload
    +----------------------------------------------------------------------+

    Extracting necessary metadata for each request...
    ... completed

    Creating upload requests on the server...
    [==================================================] 100%
    Initializing upload
    ... completed

    Starting upload of selected units. If this process is stopped through ctrl+c,
    the uploads will be paused and may be resumed later using the resume command or
    canceled entirely using the cancel command.

    Importing into the repository...
    ... completed

    Deleting the upload request...
    ... completed

And now we are able to see that our errata is part of the repo::

    $ pulp-admin rpm repo content errata --repo-id=repo --match type=bugzilla
    Description:      1: pulp-test-package now conserves your precious bits.
    From Str:         pulp-list@redhat.com
    Id:               DEMO_ID_1
    Issued:           Wed Dec 19 12:19:18 EST 2012
    Pkglist:          
      Name:     el6
      Packages: 
        Arch:     x86_64
        Epoch:    0
        Filename: pulp-test-package-0.3.1-1.fc11.x86_64.rpm
        Name:     pulp-test-package
        Release:  1.fc11
        Src:      pulp-test-package-0.3.1-1.fc11.src.rpm
        Sums:     6bce3f26e1fc0fc52ac996f39c0d0e14fc26fb8077081d5b4dbfb6431b08aa9f
        Type:     sha256
        Version:  0.3.1
      Short:    
    Pushcount:        1
    Reboot Suggested: False
    References:       
      Href:  http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=123456
      Id:    123456
      Title: pulp-test-package-0.2.1 prints mean error messages to users
      Type:  bugzilla
      Href:  http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=654321
      Id:    654321
      Title: pulp-test-package-0.2.1 causes users' machines to run out of
             bits/bytes/whatever. The users must wait until the next supply comes
             next week
      Type:  bugzilla
    Release:          el6
    Rights:           None
    Severity:         None
    Solution:         None
    Status:           final
    Summary:          None
    Title:            1: pulp-test-package bit conservation
    Type:             bugzilla
    Updated:          Wed Dec 19 12:19:18 EST 2012
    Version:          1

Package Groups
==============

.. _creating_package_groups:

Create Your Own Package Groups
------------------------------

You can easily define your own package groups with the :command:`pulp_admin`
utility. Let's create and sync a repo::

    $ pulp-admin rpm repo create --repo-id=repo_1 \
      --feed=http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/pulp_unittest/
    Successfully created repository [repo_1]

    $ pulp-admin rpm repo sync run --repo-id=repo_1

Now let's build a package group for our demo repo test files::

   $ pulp-admin rpm repo uploads group --repo-id=repo_1 --group-id=pulp_test \
     --name="Pulp Test" --description="A package group of Pulp test files." \
     --mand-name=pulp-dot-2.0-test --mand-name=pulp-test-package
   +----------------------------------------------------------------------+
                                 Unit Upload
   +----------------------------------------------------------------------+

   Extracting necessary metadata for each request...
   ... completed

   Creating upload requests on the server...
   [==================================================] 100%
   Initializing upload
   ... completed

   Starting upload of selected units. If this process is stopped through ctrl+c,
   the uploads will be paused and may be resumed later using the resume command or
   canceled entirely using the cancel command.

   Importing into the repository...
   ... completed

   Deleting the upload request...
   ... completed

We can see that the package group is now part of our repo::

   $ pulp-admin rpm repo content group --repo-id=repo_1 --match id=pulp_test
   Conditional Package Names:
   Default:                   False
   Default Package Names:     None
   Description:               A package group of Pulp test files.
   Display Order:             0
   Id:                        pulp_test
   Langonly:                  None
   Mandatory Package Names:   pulp-dot-2.0-test, pulp-test-package
   Name:                      Pulp Test
   Optional Package Names:    None
   Repo Id:                   repo_1
   Translated Description:
   Translated Name:
   User Visible:              False

Copying Package Groups Between Repos
------------------------------------

Package groups can be copied from one repository to another, which will bring
along the packages it references as well. For this example, we will assume
you've performed the steps from the :ref:`creating_package_groups` section.

We'll begin by creating a new empty repo, ``repo_2``::

   $ pulp-admin rpm repo create --repo-id=repo_2
   Successfully created repository [repo_2]

And now we will copy our package group, ``pulp_test`` from ``repo_1`` to
``repo_2``::

   $ pulp-admin rpm repo copy group --match id=pulp_test --from-repo-id=repo_1 \
     --to-repo-id=repo_2
   Progress on this task can be viewed using the commands under "repo tasks".

.. note::
  Use the --recursive flag to copy any dependencies of units being copied from the source repo
  into the destination repo.

This task should complete fairly quickly since there isn't much to do with our
tiny example repo, but we can check on the progress to verify that it is
finished::

    $ pulp-admin repo tasks list --repo-id=repo_1
    +----------------------------------------------------------------------+
                                     Tasks
    +----------------------------------------------------------------------+

    Operations:  associate
    Resources:   repo_2 (repository), repo_1 (repository)
    State:       Successful
    Start Time:  2012-12-20T16:26:44Z
    Finish Time: 2012-12-20T16:26:44Z
    Result:      N/A
    Task Id:     9f1d0146-cc28-47a8-b0f4-b1b49f84e058

Now we can inspect ``repo_2`` and see that the package group and its RPMs have
been copied there::

    $ pulp-admin rpm repo content group --repo-id=repo_2
    Conditional Package Names:
    Default:                   False
    Default Package Names:     None
    Description:               A package group of Pulp test files.
    Display Order:             0
    Id:                        pulp_test
    Langonly:                  None
    Mandatory Package Names:   pulp-dot-2.0-test, pulp-test-package
    Name:                      Pulp Test
    Optional Package Names:    None
    Repo Id:                   repo_1
    Translated Description:
    Translated Name:
    User Visible:              False

    $ pulp-admin rpm repo content rpm --repo-id=repo_2
    Arch:         x86_64
    Buildhost:    gibson
    Checksum:     435d92e6c09248b501b8d2ae786f92ccfad69fab8b1bc774e2b66ff6c0d83979
    Checksumtype: sha256
    Description:  Test package to see how we deal with packages with dots in the
                  name
    Epoch:        0
    Filename:     pulp-dot-2.0-test-0.1.2-1.fc11.x86_64.rpm
    License:      MIT
    Name:         pulp-dot-2.0-test
    Provides:     [[u'pulp-dot-2.0-test(x86-64)', u'EQ', [u'0', u'0.1.2',
                  u'1.fc11']], [u'pulp-dot-2.0-test', u'EQ', [u'0', u'0.1.2',
                  u'1.fc11']], [u'config(pulp-dot-2.0-test)', u'EQ', [u'0',
                  u'0.1.2', u'1.fc11']]]
    Release:      1.fc11
    Requires:
    Vendor:
    Version:      0.1.2

    Arch:         x86_64
    Buildhost:    gibson
    Checksum:     6bce3f26e1fc0fc52ac996f39c0d0e14fc26fb8077081d5b4dbfb6431b08aa9f
    Checksumtype: sha256
    Description:  Test package.  Nothing to see here.
    Epoch:        0
    Filename:     pulp-test-package-0.3.1-1.fc11.x86_64.rpm
    License:      MIT
    Name:         pulp-test-package
    Provides:     [[u'pulp-test-package(x86-64)', u'EQ', [u'0', u'0.3.1',
                  u'1.fc11']], [u'pulp-test-package', u'EQ', [u'0', u'0.3.1',
                  u'1.fc11']], [u'config(pulp-test-package)', u'EQ', [u'0',
                  u'0.3.1', u'1.fc11']]]
    Release:      1.fc11
    Requires:
    Vendor:
    Version:      0.3.1

Package Categories
==================

.. _creating_package_categores:

Create Your Own Package Categories
----------------------------------

You can also define your own package categories with the :command:`pulp_admin`
utility. Let's create and sync a repo::

    $ pulp-admin rpm repo create --repo-id=repo_1 \
      --feed=http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/pulp_unittest/
    Successfully created repository [repo_1]

    $ pulp-admin rpm repo sync run --repo-id=repo_1

Now let's build two package groups for our demo repo test files::

   $ pulp-admin rpm repo uploads group --repo-id=repo_1 \
     --group-id=pulp_test_packages --name="Pulp Test Packages" \
     --description="A package group of Pulp test files." \
     --mand-name=pulp-dot-2.0-test --mand-name=pulp-test-package

   $ pulp-admin rpm repo uploads group --repo-id=repo_1 \
     --group-id=pulp_dotted_name_packages --name="Pulp Dotted Name Packages" \
     --description="A group of packages that have dots in their names." \
     --mand-name=pulp-dot-2.0-test

And now we can easily create a package category that is a collection of these
two groups::

    $ pulp-admin rpm repo uploads category --repo-id=repo_1 \
      --category-id=example_category --name="Example Category" \
      --description="An Example Category" --group=pulp_test_packages \
      --group=pulp_dotted_name_packages
    +----------------------------------------------------------------------+
                                  Unit Upload
    +----------------------------------------------------------------------+

    Extracting necessary metadata for each request...
    ... completed

    Creating upload requests on the server...
    [==================================================] 100%
    Initializing upload
    ... completed

    Starting upload of selected units. If this process is stopped through ctrl+c,
    the uploads will be paused and may be resumed later using the resume command or
    canceled entirely using the cancel command.

    Importing into the repository...
    ... completed

    Deleting the upload request...
    ... completed

The package category details can be listed as well::

    $ pulp-admin rpm repo content category --repo-id=repo_1 \
      --match id=example_category
    Description:            An Example Category
    Display Order:          0
    Id:                     example_category
    Name:                   Example Category
    Packagegroupids:        pulp_test_packages, pulp_dotted_name_packages
    Repo Id:                repo_1
    Translated Description:
    Translated Name:

Copying Package Categories
--------------------------

Like package groups, categories can be copied between repos, which will bring
along their groups and packages. Assuming you've performed the steps from the
:ref:`creating_package_categores` section, let's begin by creating an empty
second repo::

    $ pulp-admin rpm repo create --repo-id=repo_2
    Successfully created repository [repo_2]

Now let's copy ``example_category`` from ``repo_1`` to ``repo_2``::

    $ pulp-admin rpm repo copy category --match id=example_category \
      --from-repo-id=repo_1 --to-repo-id=repo_2
    Progress on this task can be viewed using the commands under "repo tasks".

.. note::
  Use the --recursive flag to copy any dependencies of units being copied from the source repo
  into the destination repo.

We should check out the task to see when it's done with the repo tasks command::

    $ pulp-admin repo tasks list --repo-id=repo_1
    +----------------------------------------------------------------------+
                                     Tasks
    +----------------------------------------------------------------------+

    Operations:  associate
    Resources:   repo_2 (repository), repo_1 (repository)
    State:       Successful
    Start Time:  2012-12-20T20:41:12Z
    Finish Time: 2012-12-20T20:41:12Z
    Result:      N/A
    Task Id:     b5139389-b985-40be-8ee5-10bc626a124a

And now we can see that ``repo_2`` has the category, groups, and RPMs::

    $ pulp-admin rpm repo content category --repo-id=repo_2
    Description:            An Example Category
    Display Order:          0
    Id:                     example_category
    Name:                   Example Category
    Packagegroupids:        pulp_test_packages, pulp_dotted_name_packages
    Repo Id:                repo_1
    Translated Description:
    Translated Name:

    $ pulp-admin rpm repo content group --repo-id=repo_2
    Conditional Package Names:
    Default:                   False
    Default Package Names:     None
    Description:               A group of packages that have dots in their names.
    Display Order:             0
    Id:                        pulp_dotted_name_packages
    Langonly:                  None
    Mandatory Package Names:   pulp-dot-2.0-test
    Name:                      Pulp Dotted Name Packages
    Optional Package Names:    None
    Repo Id:                   repo_1
    Translated Description:
    Translated Name:
    User Visible:              False

    Conditional Package Names:
    Default:                   False
    Default Package Names:     None
    Description:               A package group of Pulp test files.
    Display Order:             0
    Id:                        pulp_test_packages
    Langonly:                  None
    Mandatory Package Names:   pulp-dot-2.0-test, pulp-test-package
    Name:                      Pulp Test Packages
    Optional Package Names:    None
    Repo Id:                   repo_1
    Translated Description:
    Translated Name:
    User Visible:              False

    $ pulp-admin rpm repo content rpm --repo-id=repo_2
    Arch:         x86_64
    Buildhost:    gibson
    Checksum:     435d92e6c09248b501b8d2ae786f92ccfad69fab8b1bc774e2b66ff6c0d83979
    Checksumtype: sha256
    Description:  Test package to see how we deal with packages with dots in the
                  name
    Epoch:        0
    Filename:     pulp-dot-2.0-test-0.1.2-1.fc11.x86_64.rpm
    License:      MIT
    Name:         pulp-dot-2.0-test
    Provides:     [[u'pulp-dot-2.0-test(x86-64)', u'EQ', [u'0', u'0.1.2',
                  u'1.fc11']], [u'pulp-dot-2.0-test', u'EQ', [u'0', u'0.1.2',
                  u'1.fc11']], [u'config(pulp-dot-2.0-test)', u'EQ', [u'0',
                  u'0.1.2', u'1.fc11']]]
    Release:      1.fc11
    Requires:
    Vendor:
    Version:      0.1.2

    Arch:         x86_64
    Buildhost:    gibson
    Checksum:     6bce3f26e1fc0fc52ac996f39c0d0e14fc26fb8077081d5b4dbfb6431b08aa9f
    Checksumtype: sha256
    Description:  Test package.  Nothing to see here.
    Epoch:        0
    Filename:     pulp-test-package-0.3.1-1.fc11.x86_64.rpm
    License:      MIT
    Name:         pulp-test-package
    Provides:     [[u'pulp-test-package(x86-64)', u'EQ', [u'0', u'0.3.1',
                  u'1.fc11']], [u'pulp-test-package', u'EQ', [u'0', u'0.3.1',
                  u'1.fc11']], [u'config(pulp-test-package)', u'EQ', [u'0',
                  u'0.3.1', u'1.fc11']]]
    Release:      1.fc11
    Requires:
    Vendor:
    Version:      0.3.1

Comps
=====

.. _upload_comps_xml_file:

Upload comps.xml file
---------------------

This is an example of creating a repo and uploading a comps.xml file into it.

::

  $ pulp-admin rpm repo create --repo-id comps-repo

  Successfully created repository [comps-repo]

  $ pulp-admin rpm repo uploads comps --repo-id comps-repo --file ~/sample-comps.xml


  +----------------------------------------------------------------------+
                                Unit Upload
  +----------------------------------------------------------------------+

  Extracting necessary metadata for each request...
  [==================================================] 100%
  Analyzing: sample-comps.xml
  ... completed

  Creating upload requests on the server...
  [==================================================] 100%
  Initializing: sample-comps.xml
  ... completed

  Starting upload of selected units. If this process is stopped through ctrl+c,
  the uploads will be paused and may be resumed later using the resume command or
  canceled entirely using the cancel command.

  Uploading: sample-comps.xml
  [==================================================] 100%
  8407/8407 bytes
  ... completed

  Importing into the repository...
  This command may be exited via ctrl+c without affecting the request.


  [\]
  Running...

  Task Succeeded


  Deleting the upload request...
  ... completed


Now let's list the repo and check its content.

::

  $ pulp-admin rpm repo list --repo-id comps-repo

  +----------------------------------------------------------------------+
                              RPM Repositories
  +----------------------------------------------------------------------+

  Id:                   comps-repo
  Display Name:         comps-repo
  Description:          None
  Content Unit Counts:  
    Package Category:    2
    Package Environment: 1
    Package Group:       3


Chili
=====

* 2 lb. Ground Beef
* Chili Powder
* Garlic
* 1 Large Onion
* 2 Cans of Tomatoes
* 4 Cans of beans (mix & match!)
* Habanero Peppers (be careful)
* Jalapeño Peppers
* 2 Bell Peppers

Put the meat, onion, powder, and tomatoes in a crock pot. Chop up all the vegetables. Put half the
vegetables and put those in the crock pot, save the rest for later in the fridge. Turn the crock pot
on for several (4-10) hours. After it is done, stir in the remaining vegetables and beans. Cook on
high for 30 minutes.
