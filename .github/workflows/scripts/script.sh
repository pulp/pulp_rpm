#!/usr/bin/env bash
# coding=utf-8

# WARNING: DO NOT EDIT!
#
# This file was generated by plugin_template, and is managed by it. Please use
# './plugin-template --github pulp_rpm' to update this file.
#
# For more info visit https://github.com/pulp/plugin_template

# make sure this script runs at the repo root
cd "$(dirname "$(realpath -e "$0")")"/../../..
REPO_ROOT="$PWD"

set -mveuo pipefail

source .github/workflows/scripts/utils.sh

export POST_SCRIPT=$PWD/.github/workflows/scripts/post_script.sh
export POST_DOCS_TEST=$PWD/.github/workflows/scripts/post_docs_test.sh
export FUNC_TEST_SCRIPT=$PWD/.github/workflows/scripts/func_test_script.sh

# Needed for both starting the service and building the docs.
# Gets set in .github/settings.yml, but doesn't seem to inherited by
# this script.
export DJANGO_SETTINGS_MODULE=pulpcore.app.settings
export PULP_SETTINGS=$PWD/.ci/ansible/settings/settings.py

export PULP_URL="https://pulp"

if [[ "$TEST" = "docs" ]]; then
  if [[ "$GITHUB_WORKFLOW" == "Rpm CI" ]]; then
    pip install towncrier==19.9.0
    towncrier --yes --version 4.0.0.ci
  fi
  cd docs
  make PULP_URL="$PULP_URL" diagrams html
  tar -cvf docs.tar ./_build
  cd ..

  if [ -f $POST_DOCS_TEST ]; then
    source $POST_DOCS_TEST
  fi
  exit
fi

if [[ "${RELEASE_WORKFLOW:-false}" == "true" ]]; then
  STATUS_ENDPOINT="${PULP_URL}${PULP_API_ROOT}api/v3/status/"
  echo $STATUS_ENDPOINT
  REPORTED_VERSION=$(http $STATUS_ENDPOINT | jq --arg plugin rpm --arg legacy_plugin pulp_rpm -r '.versions[] | select(.component == $plugin or .component == $legacy_plugin) | .version')
  response=$(curl --write-out %{http_code} --silent --output /dev/null https://pypi.org/project/pulp-rpm/$REPORTED_VERSION/)
  if [ "$response" == "200" ];
  then
    echo "pulp_rpm $REPORTED_VERSION has already been released. Skipping running tests."
    exit
  fi
fi

if [[ "$TEST" == "plugin-from-pypi" ]]; then
  COMPONENT_VERSION=$(http https://pypi.org/pypi/pulp-rpm/json | jq -r '.info.version')
  git checkout ${COMPONENT_VERSION} -- pulp_rpm/tests/
fi

cd ../pulp-openapi-generator
./generate.sh pulpcore python
pip install ./pulpcore-client
rm -rf ./pulpcore-client
if [[ "$TEST" = 'bindings' ]]; then
  ./generate.sh pulpcore ruby 0
  cd pulpcore-client
  gem build pulpcore_client.gemspec
  gem install --both ./pulpcore_client-0.gem
fi
cd $REPO_ROOT

if [[ "$TEST" = 'bindings' ]]; then
  if [ -f $REPO_ROOT/.ci/assets/bindings/test_bindings.py ]; then
    python $REPO_ROOT/.ci/assets/bindings/test_bindings.py
  fi
  if [ -f $REPO_ROOT/.ci/assets/bindings/test_bindings.rb ]; then
    ruby $REPO_ROOT/.ci/assets/bindings/test_bindings.rb
  fi
  exit
fi

cat unittest_requirements.txt | cmd_stdin_prefix bash -c "cat > /tmp/unittest_requirements.txt"
cmd_prefix pip3 install -r /tmp/unittest_requirements.txt

# check for any uncommitted migrations
echo "Checking for uncommitted migrations..."
cmd_prefix bash -c "django-admin makemigrations --check --dry-run"

if [[ "$TEST" != "upgrade" ]]; then
  # Run unit tests.
  cmd_prefix bash -c "PULP_DATABASES__default__USER=postgres pytest -v -r sx --color=yes -p no:pulpcore --pyargs pulp_rpm.tests.unit"
fi

# Run functional tests
export PYTHONPATH=$REPO_ROOT${PYTHONPATH:+:${PYTHONPATH}}

if [[ "$TEST" == "performance" ]]; then
  if [[ -z ${PERFORMANCE_TEST+x} ]]; then
    pytest -vv -r sx --color=yes --pyargs --capture=no --durations=0 pulp_rpm.tests.performance
  else
    pytest -vv -r sx --color=yes --pyargs --capture=no --durations=0 pulp_rpm.tests.performance.test_$PERFORMANCE_TEST
  fi
  exit
fi

if [ -f $FUNC_TEST_SCRIPT ]; then
  source $FUNC_TEST_SCRIPT
else

    if [[ "$GITHUB_WORKFLOW" == "Rpm Nightly CI/CD" ]]; then
        pytest -v -r sx --color=yes --suppress-no-test-exit-code --pyargs pulp_rpm.tests.functional -m parallel -n 8
        pytest -v -r sx --color=yes --pyargs pulp_rpm.tests.functional -m "not parallel"

    
        pytest -v -r sx --color=yes --suppress-no-test-exit-code --pyargs pulpcore.tests.functional -m "from_pulpcore_for_all_plugins and parallel" -n  8
        pytest -v -r sx --color=yes --suppress-no-test-exit-code --pyargs pulpcore.tests.functional -m "from_pulpcore_for_all_plugins and not parallel"
    
    else
        pytest -v -r sx --color=yes --suppress-no-test-exit-code --pyargs pulp_rpm.tests.functional -m "parallel and not nightly" -n 8
        pytest -v -r sx --color=yes --pyargs pulp_rpm.tests.functional -m "not parallel and not nightly"

    
        pytest -v -r sx --color=yes --suppress-no-test-exit-code --pyargs pulpcore.tests.functional -m "from_pulpcore_for_all_plugins and not nightly and parallel" -n  8
        pytest -v -r sx --color=yes --suppress-no-test-exit-code --pyargs pulpcore.tests.functional -m "from_pulpcore_for_all_plugins and not nightly and not parallel"
    
    fi

fi
export PULP_FIXTURES_URL="http://pulp-fixtures:8080"
pushd ../pulp-cli
pytest -v -m pulp_rpm
popd

if [ -f $POST_SCRIPT ]; then
  source $POST_SCRIPT
fi
