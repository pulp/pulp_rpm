User setup
==========

Install ``pulpcore``
--------------------

Follow the `installation
instructions <https://docs.pulpproject.org/en/3.0/nightly/installation/instructions.html>`__
provided with pulpcore.

Install ``pulp_rpm``
--------------------

Users should install from **either** PyPI or source or use ansible-pulp installer.

.. _ansible-installation:

Install with Ansible-pulp
*************************

With the use of the ``ansible-pulp`` installer you need to download a supportive
role before you run installer.

Only Fedora 29+ and CentOS 7 (with epel repository and python36) are supported.

.. code-block:: bash

   git clone https://github.com/pulp/ansible-pulp.git
   cd ansible-pulp
   ansible-galaxy install pulp.pulp_rpm_prerequisites -p ./roles/

Then use role you downloaded **before** ansible-pulp installer roles.
Do not forget to set ``pulp_use_system_wide_pkgs`` to ``true``.

.. code-block:: yaml

   ---
   - hosts: all
     vars:
       pulp_secret_key: secret
       pulp_default_admin_password: password
       pulp_use_system_wide_pkgs: true
       pulp_install_plugins:
         pulp-rpm:
           app_label: "rpm"
     roles:
       - pulp.pulp_rpm_prerequisites
       - pulp-database
       - pulp-workers
       - pulp-resource-manager
       - pulp-webserver
       - pulp-content
     environment:
       DJANGO_SETTINGS_MODULE: pulpcore.app.settings

Now you can run installer against your desired host following instructions
in the ansible-pulp installer.


Install ``createrepo_c`` from source
************************************

``pulp_rpm`` depends on a Python package named ``createrepo_c``, which is compiled from a C
library. Unfortunately, this package is currently only available as a Python "source distribution",
meaning that it must be compiled on your own machine. But, luckily, you won't have to do that yourself!
Simply install the build dependencies on your machine and the build process itself will happen behind
the scenes when you install the package.

Caveat: Unfortunately, a fully-featured ``createrepo_c`` can only be built on Red Hat based distros,
as not all of build dependencies are available on Debian-based platforms.

If you are on Fedora, install the build dependencies with this command:

.. code-block:: bash

   sudo dnf install -y gcc make cmake bzip2-devel expat-devel file-devel glib2-devel libcurl-devel libmodulemd-devel libxml2-devel python3-devel rpm-devel openssl-devel sqlite-devel xz-devel zchunk-devel zlib-devel

If on CentOS or RHEL, use this command:

.. code-block:: bash

   sudo yum install -y gcc make cmake bzip2-devel expat-devel file-devel glib2-devel libcurl-devel libmodulemd-devel libxml2-devel python36-devel rpm-devel openssl-devel sqlite-devel xz-devel zchunk-devel zlib-devel

Install ``pulp_rpm`` from source
********************************

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   git clone https://github.com/pulp/pulp_rpm.git
   cd pulp_rpm
   pip install -e .

Install ``pulp-rpm`` From PyPI
******************************

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   pip install pulp-rpm

Run Migrations
**************

.. code-block:: bash

   django-admin migrate rpm

Run Services
------------

.. code-block:: bash

   django-admin runserver 24817
   gunicorn pulpcore.content:server --bind 'localhost:24816' --worker-class 'aiohttp.GunicornWebWorker' -w 2
   sudo systemctl restart pulpcore-resource-manager
   sudo systemctl restart pulpcore-worker@1
   sudo systemctl restart pulpcore-worker@2
