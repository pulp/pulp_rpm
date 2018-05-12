#!/usr/bin/env sh
set -v

flake8 --config flake8.cfg || exit 1

result=0

pulp-manager migrate auth --noinput
pulp-manager makemigrations pulp_app --noinput
pulp-manager makemigrations pulp_rpm
pulp-manager migrate --noinput
if [ $? -ne 0 ]; then
  result=1
fi

# pushd ../pulp
# coverage run manage.py test pulp_rpm.tests.unit
#   if [ $? -ne 0 ]; then
#     result=1
# fi
# popd

pulp-manager reset-admin-password --password admin
pulp-manager runserver >>~/django_runserver.log 2>&1 &
rq worker -n resource_manager@%h -w 'pulpcore.tasking.worker.PulpWorker' >>~/resource_manager.log 2>&1 &
rq worker -n reserved_resource_worker_1@%h -w 'pulpcore.tasking.worker.PulpWorker' >>~/reserved_workers-1.log 2>&1 &
# sleep 5
# py.test -v --color=yes --pyargs ./pulp_rpm/tests/functional/
# if [ $? -ne 0 ]; then
#   result=1
# fi

cat ~/django_runserver.log
cat ~/resource_manager.log
cat ~/reserved_workers-1.log

exit $result
