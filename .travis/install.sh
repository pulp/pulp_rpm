#!/usr/bin/env sh
set -v

export COMMIT_MSG=$(git show HEAD^2 -s)
export PULP_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/pulp\/pull\/(\d+)' | awk -F'/' '{print $7}')

pip install -r test_requirements.txt

cd .. && git clone https://github.com/pulp/pulp.git

if [ -n "$PULP_PR_NUMBER" ]; then
  pushd pulp
  git fetch origin +refs/pull/$PULP_PR_NUMBER/merge
  git checkout FETCH_HEAD
  popd
fi

pushd pulp/pulpcore/ && pip install -e . && popd
pushd pulp/plugin/ && pip install -e .  && popd


### Install createrepo_c build deps ###
sudo apt-get update -y
sudo apt-get install -y gcc libbz2-dev cmake libexpat1-dev libmagic-dev libglib2.0-dev libcurl4-openssl-dev libxml2-dev libpython3-dev librpm-dev libssl-dev libsqlite3-dev liblzma-dev zlib1g-dev

pip install scikit-build
pip install https://repos.fedorapeople.org/pulp/pulp/python-packages/createrepo_c-0.11.1.tar.gz
#######################################

cd pulp_rpm
pip install -e .
