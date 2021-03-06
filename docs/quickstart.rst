Quickstart
==========

Run Pulplift
------------

Use pulplift to try out Pulp. Pulplift uses `Vagrant <https://www.vagrantup.com/docs/installation/>`_ so you'll need to have that installed.

Download pulplift.

::

    git clone --recurse-submodules https://github.com/pulp/pulplift.git
    cd pulplift


Use ``example.user-config.yml`` as a template for your config yaml file or directly edit that one.

::

    cp example.user-config.yml local.user-config.yml

Edit the config file as show below.

.. code-block:: yaml

    pulp_default_admin_password: password
    pulp_install_plugins:
      pulp-rpm: {}
      pulp-file: {}

    pulp_settings:
      secret_key: "unsafe_default"


Start your box and ssh to it

::

    vagrant up pulp3-sandbox-fedora30
    vagrant ssh pulp3-sandbox-fedora30


Be sure you are running your pulp environment

::

    workon pulp


Check Pulp's Status
-------------------

Check the status API using ``httpie``

::

    sudo dnf install httpie -y
    http :24817/pulp/api/v3/status/  # This should show the status API


Next Steps
----------

* Sync rpms from the zoo repo using the :ref:`sync-publish-workflow`.
* Configure a client to :ref:`download packages <get-content-workflow>` from a RPM repository hosted
  by Pulp.
