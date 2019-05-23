Quickstart
==========

Run Pulplift
------------

Use pulplift to try out Pulp. From `their quickstart <https://github.com/pulp/pulplift#quickstart>`_
pulplift uses `Vagrant <https://www.vagrantup.com/docs/installation/>`_ so you'll need to have that
installed.

::

    git clone --recurse-submodules https://github.com/pulp/pulplift.git
    cd pulplift


Create your pulp_rpm.yaml playbook with these contents:

.. code-block:: yaml

   ---
   - hosts: all
     vars:
       pulp_secret_key: secret
       pulp_default_admin_password: password
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


Install the dependency bootstrapping role ``pulp.pulp_rpm_prerequisites``:

    ansible-galaxy install pulp.pulp_rpm_prerequisites -p ./roles/


Start your box, run ansible on it, ssh to your box::

    vagrant up fedora30
    ansible-playbook pulp_rpm.yaml -l fedora30
    vagrant ssh fedora30


Check Pulp's Status
-------------------

Check the status API using ``httpie``::

    sudo dnf install httpie -y
    http :24817/pulp/api/v3/status/  # This should show the status API


Next Steps
----------

* Sync rpms "lazily" from the zoo repo using the :ref:`sync-publish-workflow`.
* Upload or mirror content using the :ref:`rpm one-shot uploader <one-shot-upload-workflow>`.
* Configure a client to :ref:`download packages <get-content-workflow>` from a RPM repository hosted
  by Pulp.
