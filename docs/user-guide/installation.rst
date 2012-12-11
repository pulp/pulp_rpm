Installation
============

.. _Pulp User Guide: http://pulp-user-guide.readthedocs.org

.. note::
  If you followed the installation instructions in the `Pulp User Guide`_,
  you already have RPM features installed. If not, this document will walk
  you through the installation.

Prerequisites
-------------

The only requirement is to meet the prerequisites of the Pulp Platform. Please
see the `Pulp User Guide`_ for prerequisites including repository setup. Also
reference that document to learn more about what each of the following components
are for.

Server
------

If you followed the Pulp User Guide install instructions, you already have RPM
support installed. If not, follow these steps.

Consider stopping Pulp. If you need Apache to keep running other web apps, or if
you need Pulp to continue serving static content, it is usually sufficient to
disable access to Pulp's REST API. That will be left as an exercise for the reader.
Otherwise, just stop Apache:

::

  $ sudo apachectl stop

Next, install the package.

::

  $ sudo yum install pulp-rpm-plugins

Then run ``pulp-manage-db`` to initialize the new types in Pulp's database.

::

  $ sudo pulp-manage-db

Finally, restart Apache.

::

  $ sudo apachectl restart

Admin Client
------------

If you followed the Pulp User Guide install instructions, you already have RPM
support installed. If not, just install the following package.

::

  $ sudo yum install pulp-rpm-admin-extensions


Consumer Client
---------------

If you followed the Pulp User Guide install instructions, you already have RPM
support installed. If not, just install the following package.

::

  $ sudo yum install pulp-rpm-consumer-extensions

Agent
-----

If you followed the Pulp User Guide install instructions, you already have RPM
support installed. If not, just install the following package.

::

  $ sudo yum install pulp-rpm-handlers

Then restart the Pulp agent.

::

  $ sudo service pulp-agent restart
