User setup
==========

.. _ansible-installation:

Install with Ansible-pulp (recommended)
---------------------------------------

With the use of the ``ansible-pulp`` installer you need to download a supportive
role before you run installer.

Only Fedora 29+ and CentOS 7 (with epel repository and python36) are supported.

.. code-block:: bash

   git clone https://github.com/pulp/ansible-pulp.git
   cd ansible-pulp
   ansible-galaxy install pulp.pulp_rpm_prerequisites -p ./roles/

Create ``playbook.yml`` as example you can use ``example-use/playbook.yml`` from ``ansible-pulp`` directory.
Do not forget about ``group_vars`` as dependency in same directory.

Add ``pulp_use_system_wide_pkgs: true`` and ``pulp_rpm`` plugin with prereq role downloaded above under the ``vars``.

Final ``playbook.yml`` can looks like:

.. code-block:: yaml

    ---
    - hosts: all
      vars:
        pulp_use_system_wide_pkgs: true
        pulp_install_plugins:
          pulp-rpm:
            prereq_role: "pulp.pulp_rpm_prerequisites"
      pre_tasks:
        # The version string below is the highest of all those in roles' metadata:
        # "min_ansible_version". It needs to be kept manually up-to-date.
        - name: Verify Ansible meets min required version
          assert:
            that: "ansible_version.full is version_compare('2.8', '>=')"
            msg: >
              "You must update Ansible to at least 2.8 to use this version of Pulp 3 Installer."
      roles:
        - pulp-database
        - pulp-workers
        - pulp-resource-manager
        - pulp-webserver
        - pulp-content
      environment:
        DJANGO_SETTINGS_MODULE: pulpcore.app.settings

Now you can run installer against your desired host following instructions
in the `ansible-pulp <https://github.com/pulp/ansible-pulp>`__ installer.


Pip install
-----------


Install ``pulpcore``
********************

Follow the `installation
instructions <https://docs.pulpproject.org/en/3.0/nightly/installation/instructions.html>`__
provided with pulpcore.

Install prerequisites
*********************

Install build dependencies
##########################

``pulp_rpm`` depends on some C libraries that must be compiled from source as Python extentions. Unfortunately,
some of these packages are only available as Python "source distributions", meaning that they must be compiled
on your own machine. But, luckily, you won't have to do that yourself! Simply install the build dependencies
on your machine and the build process itself will happen behind the scenes when you install the packages.

Caveat: Unfortunately, a fully-featured ``createrepo_c`` can only be built on Red Hat based distros,
as not all of its build dependencies are available on Debian-based platforms.

If you are on Fedora, install the build dependencies with this command:

.. code-block:: bash

   sudo dnf install -y gcc make cmake bzip2-devel expat-devel file-devel glib2-devel libcurl-devel libmodulemd-devel libxml2-devel python3-devel python3-gobject python3-libmodulemd rpm-devel openssl-devel sqlite-devel xz-devel zchunk-devel zlib-devel

If on CentOS or RHEL, use this commands:

Ensure you have enabled ``epel`` repository

.. code-block:: bash

    sudo yum install -y epel-release

.. code-block:: bash

   sudo yum install -y gcc make cmake bzip2-devel expat-devel file-devel glib2-devel libcurl-devel libmodulemd2-devel ninja-build libxml2-devel python36-devel python36-gobject rpm-devel openssl-devel sqlite-devel xz-devel zchunk-devel zlib-devel


Ensure your virtual environment uses system wide packages
#########################################################

``pyevn.cfg`` can be found usually in ``/usr/local/lib/pulp/`` as root directory of virtual environment.

.. code-block:: bash

    grep "include-system-site-packages" pyvenv.cfg

You should get ``include-system-site-packages = true``.

This is a necessary prerequisite for ``libmodulemd`` and ``libcomps`` along with the build dependencies listed
above for ``createrepo_c``.

Install Python build dependencies (CentOS / RHEL only)
######################################################

Users on CentOS or RHEL must manually install the Python build dependencies for createrepo_c and libcomps.

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   pip install scikit-build nose

Install ``pulp_rpm``
********************

Users should install from **either** PyPI or source or use ansible-pulp installer.
In case of PyPI or source installation in virtual environment make sure the environment
has enabled usage of system wide packages. You can achieve that with flag ``--system-site-packages``
at environment creation time or with option in ``pyvenv.cfg`` file in root directory of virtual environment.


Install ``pulp-rpm`` From PyPI
##############################

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   pip install pulp-rpm

Install ``pulp_rpm`` from source
################################

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   git clone https://github.com/pulp/pulp_rpm.git
   cd pulp_rpm
   pip install -e .

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
