Introduction
============

RPM Support for Pulp allows you to create and publish repositories of RPM
packages (including RPM, SRPM, DRPM, errata, and distributions).

* Automatically retrieve packages from external repositories and store them in
  local Pulp repositories, which are hosted by the Pulp server.
* Upload your own packages and errata into local Pulp repositories.
* Copy packages and errata from one local repository to another, enabling you to promote
  testing versions to a production repository.
* Push packages out to large numbers of consumers.
* Track from the server what packages are installed on each consumer.


How to Use This Guide
---------------------

This guide documents features and concepts that are specific to RPM support. The
Pulp User Guide (available `here <http://www.pulpproject.org/docs/>`_) has much
more information about how to perform common operations like search repositories,
copy packages from one repository to another, etc. As such, the Pulp User Guide
should be used in conjunction with this guide.

You will also find that the ``pulp-admin`` and ``pulp-consumer`` command line
utilities have thorough help text available by appending ``--help`` to any command
or section.
