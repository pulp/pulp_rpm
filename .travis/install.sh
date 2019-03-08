#!/usr/bin/env sh
set -v

export COMMIT_MSG=$(git show HEAD^2 -s)
export PULP_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/pulpcore\/pull\/(\d+)' | awk -F'/' '{print $7}')
export PULP_PLUGIN_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/pulpcore-plugin\/pull\/(\d+)' | awk -F'/' '{print $7}')
export PULP_SMASH_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/PulpQE\/pulp-smash\/pull\/(\d+)' | awk -F'/' '{print $7}')

pip install -r test_requirements.txt

cd .. && git clone https://github.com/pulp/pulpcore.git

if [ -n "$PULP_PR_NUMBER" ]; then
  pushd pulpcore
  git fetch origin +refs/pull/$PULP_PR_NUMBER/merge
  git checkout FETCH_HEAD
  popd
fi

pip install -e ./pulpcore[postgres]

git clone https://github.com/pulp/pulpcore-plugin.git

if [ -n "$PULP_PLUGIN_PR_NUMBER" ]; then
  pushd pulpcore-plugin
  git fetch origin +refs/pull/$PULP_PLUGIN_PR_NUMBER/merge
  git checkout FETCH_HEAD
  popd
fi

pip install -e ./pulpcore-plugin

if [ -n "$PULP_SMASH_PR_NUMBER" ]; then
  pip uninstall -y pulp-smash
  git clone https://github.com/PulpQE/pulp-smash.git
  pushd pulp-smash
  git fetch origin +refs/pull/$PULP_SMASH_PR_NUMBER/merge
  git checkout FETCH_HEAD
  popd
  pip install -e ./pulp-smash
fi

### Install createrepo_c build deps ###
sudo apt-get update -y
sudo apt-get install -y gcc libbz2-dev cmake libexpat1-dev libmagic-dev libglib2.0-dev libcurl4-openssl-dev libxml2-dev libpython3-dev librpm-dev libssl-dev libsqlite3-dev liblzma-dev zlib1g-dev
pip install createrepo_c --install-option="--" --install-option="-DWITH_ZCHUNK:BOOL=OFF"
#######################################

cd pulp_rpm
pip install -e .
