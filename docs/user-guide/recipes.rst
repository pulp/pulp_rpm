Recipes
=======


Mirror Something
----------------


Use a Proxy
-----------


Sync a Protected Repo
---------------------


Publish a Protected Repo
------------------------


Publish ISOs
------------

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
to ``repo_2``. I can determine which errata are RHSA by using a regex filter::

    $ pulp-admin rpm repo content errata --filters='{"id": {"$regex": "^RHSA"}}' \
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

    $ pulp-admin rpm repo copy errata --filters='{"id": {"$regex": "^RHSA"}}' \
    > --from-repo-id=repo_1 --to-repo-id=repo_2
    Progress on this task can be viewed using the commands under "repo tasks".

We can inspect the progress of this operation using
:command:`pulp-admin repo tasks list --repo-id=repo_1`. There are only a few
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

.. others?

