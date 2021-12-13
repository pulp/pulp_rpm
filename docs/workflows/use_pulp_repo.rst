.. _get-content-workflow:

Get content from Pulp
=====================

When content is published and distributed, one can download packages directly from Pulp or point
client tools to a repo distributed by Pulp.


Download ``foo.rpm`` from Pulp
------------------------------
Using pulp-cli commands :

.. literalinclude:: ../_scripts/download_cli.sh
   :language: bash

Using httpie to talk directly to the REST API :

.. literalinclude:: ../_scripts/download.sh
   :language: bash

Download GET response:

.. code:: shell

    HTTP/1.1 200 OK
    Accept-Ranges: bytes
    AppTime: D=417
    Cache-Control: max-age=1800
    Connection: keep-alive
    Content-Length: 2473
    Content-Type: application/x-rpm
    Date: Wed, 27 Nov 2019 14:17:43 GMT
    Etag: "9a9-598026a4cfb06"
    Expires: Wed, 27 Nov 2019 14:47:43 GMT
    Last-Modified: Sat, 23 Nov 2019 12:10:24 GMT
    Server: nginx/1.16.1
    Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
    X-Fedora-AppServer: people02.fedoraproject.org
    X-GitProject: (null)

    +-----------------------------------------+
    | NOTE: binary data not shown in terminal |
    +-----------------------------------------+

Install a package from Pulp
---------------------------
Download the config.repo file from the server at distribution's
base_path and store it in /etc/yum.repos.d::

  curl http://localhost:24816/pulp/content/foo/config.repo > /etc/yum.repos.d/foo.repo

Now use dnf to install a package::

  sudo dnf install walrus

List and Install applicable Advisories
--------------------------------------

Make sure Pulp repo is configured in /etc/yum.repos.d/, then use dnf to work with Advisory content.

List applicable Advisories:

``$ dnf list-sec``

Install a specific advisory:

``sudo dnf update --advisory XXXX-XXXX:XXXX``
