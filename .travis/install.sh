#!/usr/bin/env sh
set -v

pip install flake8 pytest git+https://github.com/PulpQE/pulp-smash.git#egg=pulp-smash

cd .. && git clone -b 3.0-dev https://github.com/pulp/pulp.git
pushd pulp/common/ && pip install -e . && popd
pushd pulp/pulpcore/ && pip install -e . && popd
pushd pulp/plugin/ && pip install -e .  && popd

cd pulp_rpm
pip install -e .
