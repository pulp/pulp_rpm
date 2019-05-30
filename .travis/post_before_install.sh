cd ../ansible-pulp
ansible-galaxy install pulp.pulp_rpm_prerequisites -p ./roles/
cd ../pulp_rpm
cp .travis/rpm_playbook.yml ../ansible-pulp/playbook.yml