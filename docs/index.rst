
``pulp_rpm`` Plugin
===================

The ``pulp_rpm`` plugin extends `pulpcore <https://pypi.python.org/pypi/pulpcore/>`__ to support
hosting RPM family content types.

Features
--------

* :ref:`sync-publish-workflow` with "RPM Content" including RPMs, Advisories, Modularity, and Comps
* :ref:`Versioned Repositories <versioned-repo-created>` so every operation is a restorable snapshot
* :ref:`Download content on-demand <create-remote>` when requested by clients to reduce disk space.
* Upload local RPM content in `chunks <https://docs.pulpproject.org/workflows/upload-publish.html#uploading-content>`__
* Add, remove, copy, and organize RPM content into various repositories
* De-duplication of all saved content
* Host content either `locally or on S3 <https://docs.pulpproject.org/installation/
  storage.html>`_
* View distributions served by pulpcore-content in a browser

Tech Preview
------------

Some additional features are being supplied as a tech preview.  There is a possibility that
backwards incompatible changes will be introduced for these particular features.  For a list of
features currently being supplied as tech previews only, see the :doc:`tech preview page
<tech-preview>`.

Requirements
------------

``pulp_rpm`` plugin requires some dependencies such as ``libsolv`` and ``libmodulemd``
which is provided only by RedHat family distributions like Fedora.

``pulp_rpm`` plugin requires either to be:

* install on Fedora 29+, CentOS 7+ (with EPEL repository enabled)
* install inside a container with ``pulplift``

Get Started
-----------

To get started, check the :doc:`installation docs<installation>` and take a look at the :doc:`basic
workflows<workflows/index>`.

Community contributions are encouraged.

* Send us pull requests on `our GitHub repository <https://github.com/pulp/pulp_rpm>`_.
* View and file issues in the `Redmine Tracker
  <https://pulp.plan.io/projects/pulp_rpm/issues>`_.


Table of Contents
-----------------

.. toctree::
   :maxdepth: 1

   installation
   settings
   quickstart
   workflows/index
   bindings
   restapi
   changes
   tech-preview
   contributing


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
