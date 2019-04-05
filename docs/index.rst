
``pulp_rpm`` Plugin
===================

The ``pulp_rpm`` plugin extends `pulpcore <https://pypi.python.org/pypi/pulpcore/>`__ to support
hosting RPM family content types.

Features
--------

* :ref:`sync-publish-workflow` with "RPM Content" including RPMs and Errata
* :ref:`Versioned Repositories <versioned-repo-created>` so every operation is a restorable snapshot
* :ref:`Lazily download content <create-remote>` when requested by clients to reduce disk space.
* Upload local RPM content :ref:`easily <one-shot-upload-workflow>`
* Copy and organize RPM content into various repositories
* De-duplication of all saved content
* Host content either `locally or on S3 <https://docs.pulpproject.org/en/3.0/nightly/installation/
  storage.html>`_

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
   workflows/index
   release-notes/3.0.z.rst


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
