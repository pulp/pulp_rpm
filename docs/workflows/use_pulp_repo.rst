Get content from Pulp
=====================

When content is published and distributed, one can download packages directly from Pulp or point
client tools to a repo distributed by Pulp.


Download ``foo.rpm`` from Pulp
------------------------------

``$ http GET http://localhost:8000/pulp/content/foo/foo.rpm``

Install a package from Pulp
---------------------------

Open /etc/yum.repos.d/foo.repo and add the following:

.. code::

  [foo]
  name = foo
  baseurl = http://localhost:8080/pulp/content/foo
  gpgcheck = 0


Now use dnf to install a package:

``$ sudo dnf install walrus``

List and Install applicable Errata
----------------------------------

Make sure Pulp repo is configured in /etc/yum.repos.d/, then use dnf to work with Errata content.

List applicable Errata:

``$ dnf list-sec``

Install a specific advisory:

``sudo dnf update --advisory XXXX-XXXX:XXXX``