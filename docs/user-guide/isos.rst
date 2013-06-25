.. _isos:

****
ISOs
****

New in Pulp RPM 2.2.0 is support in the admin client extensions for ISO content. The ISO client
supports the following features around ISO repositories:

Features
========

* Create repositories
* Update repositories
* Delete repositories
* List repositories
* Copy ISOs between repositories
* Search for ISOs within a given repository
* Remove ISOs from a repository
* Upload ISOs to a repository
* Sync an ISO repository with a ISO feed
* Publish ISO repositories

We will not endeavor to document all of these feature thoroughly here, as they are pretty well
documented in the admin client extensions themselves. All ISO repo features are documented in the
help text of the admin client's new ``iso repo`` section::

    $ pulp-admin iso repo

Recipes
=======

Syncing an ISO Repository
-------------------------

In this recipe, we will create an ISO repository with an upstream feed, and we will synchronize it.

Let's begin by creating the repository::

    $ pulp-admin iso repo create --repo-id example --feed http://pkilambi.fedorapeople.org/test_file_repo/ --serve-http true
    Successfully created repository [example]

In this command, we've created an ISO repository that syncs with the given feed URL, and we've also
instructed it to publish over HTTP.

.. note::

    The ISO repository can only sync against feeds that publish a manifest file called
    PULP_MANIFEST. Most ISO collections on the Internet do not publish a PULP_MANIFEST file
    alongside their ISOs, and those collections cannot be consumed by the ISO Importer. The importer
    will append a trailing slash to the ``--feed`` setting if it doesn't already have one, and then
    will perform a URL join with the feed and the name ``PULP_MANIFEST`` to determine where it
    should look for the manifest. Please ensure that a PULP_MANIFEST is available at the URL you
    give to the ``--feed`` setting here.

Now that we've created the repository, let's sync it as well::

    $ pulp-admin iso repo sync run --repo-id example
    +----------------------------------------------------------------------+
                       Synchronizing Repository [example]
    +----------------------------------------------------------------------+

    This command may be exited by pressing ctrl+c without affecting the actual
    operation on the server.

    Downloading the Pulp Manifest...
    The Pulp Manifest was downloaded successfully.

    Downloading 3 ISOs...
    [==================================================] 100%
    ISOs: 3/3	Data: 10.2 MB/10.2 MB	Avg: 1.7 MB/s


    Successfully downloaded 3 ISOs.

    The repository was successfully published.

ISO repositories auto-publish by default, so you can now browse to
http://<your-server>/pulp/isos/example/ and view the downloaded ISOs.

Uploading ISOs to a Repository
------------------------------

You can also upload your own ISOs to a repository. Let's begin by creating a repository::

    $ pulp-admin iso repo create --repo-id uploads --serve-http true
    Successfully created repository [uploads]

We didn't give this one a feed, but we still instructed it to publish over HTTP. Let's upload a
file::

    $ pulp-admin iso repo uploads upload --repo-id uploads -f ~/Desktop/Fedora-17-x86_64-Live-Desktop.iso
    +----------------------------------------------------------------------+
                                  Unit Upload
    +----------------------------------------------------------------------+

    Extracting necessary metadata for each request...
    [==================================================] 100%
    Analyzing: Fedora-17-x86_64-Live-Desktop.iso
    ... completed

    Creating upload requests on the server...
    [==================================================] 100%
    Initializing: Fedora-17-x86_64-Live-Desktop.iso
    ... completed

    Starting upload of selected units. If this process is stopped through ctrl+c,
    the uploads will be paused and may be resumed later using the resume command or
    cancelled entirely using the cancel command.

    Uploading: Fedora-17-x86_64-Live-Desktop.iso
    [==================================================] 100%
    676331520/676331520 bytes
    ... completed

    Importing into the repository...
    ... completed

    Deleting the upload request...
    ... completed

In this example, we uploaded the Fedora 17 ISO from our Desktop. We have not published the
repository, and Pulp repositories do not auto publish after uploads, so let's now publish the
repository::

    $ pulp-admin iso repo publish run --repo-id uploads
    +----------------------------------------------------------------------+
                        Publishing Repository [uploads]
    +----------------------------------------------------------------------+

    This command may be exited by pressing ctrl+c without affecting the actual
    operation on the server.

    The repository was successfully published.

You can now browse to http://<your-server>/pulp/isos/uploads/ and view the ISO you've uploaded, as
well as the generated PULP_MANIFEST file.
