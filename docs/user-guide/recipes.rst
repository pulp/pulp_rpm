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

