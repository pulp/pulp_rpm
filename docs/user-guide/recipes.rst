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

To keep the repository current, it might be desirable to synchronize it on a
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

.. _search-errata:

Searching for Errata
--------------------

Pulp has a very powerful search interface that can be used to search content
units. In this recipe, you will learn how to use it to search for errata that
have been issued on or after a date, and also how to search for errata by type.
Let's start by defining a repo cleverly called ``repo`` with a demo feed::

    $ pulp-admin rpm repo create --repo-id=repo \
    > --feed=http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/pulp_unittest/ \
    > --relative-url=repo
    Successfully created repository [repo]

Now let's sync the repo so it has some errata for us to search::

    $ pulp-admin rpm repo sync run --repo-id=repo

The contents of our example repository are from a few years ago, but it includes
errata over a span of a few years. Suppose that I wanted to know which errata
were issued on or after December 1, 2009. For this example, I will include the
``--fields=id`` flag to limit the output to just be the IDs of the errata, but
you can season that flag to taste, or omit it if you want to see everything::

    $ pulp-admin rpm repo content errata --filters='{"issued": {"$gte": "2009-12-01"}}' \
    > --repo-id=repo --fields=id
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

    $ pulp-admin rpm repo content errata --match="type=security" \
    > --repo-id=repo --fields=id
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
    > --filters='{"id": {"$regex": "^RHSA"}}' --repo-id=repo

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
    > --feed=http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/pulp_unittest/ \
    > --relative-url=repo_1
    Successfully created repository [repo_1]

    $ pulp-admin rpm repo create --repo-id=repo_2 \
    > --relative-url=repo_2
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
                       Tree Files: 3/3 items
                       Files:      0/0 items
                       ... completed

                       Importing errata...
                       [|]
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
to ``repo_2``. We can determine which errata are RHSA by using a regex filter::

    $ pulp-admin rpm repo content errata --match="type=security" \
    > --repo-id=repo_1 --fields=id
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

    $ pulp-admin rpm repo copy errata --match="type=security" \
    > --from-repo-id=repo_1 --to-repo-id=repo_2
    Progress on this task can be viewed using the commands under "repo tasks".

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
    > --feed=http://repos.fedorapeople.org/repos/pulp/pulp/demo_repos/pulp_unittest/
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
    > --title="1: pulp-test-package bit conservation" \
    > --description="1: pulp-test-package now conserves your precious bits." \
    > --version=1 --release="el6" --type="bugzilla" --status="final" \
    > --updated="`date`" --issued="`date`" --reference-csv=references.csv \
    > --pkglist-csv=package_list.csv --from=pulp-list@redhat.com --repo-id=repo
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
    cancelled entirely using the cancel command.

    Importing into the repository...
    ... completed

    Deleting the upload request...
    ... completed

And now we are able to see that our errata is part of the repo::

    $ pulp-admin rpm repo content errata --repo-id=repo --match="type=bugzilla"
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
