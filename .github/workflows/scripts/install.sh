#!/usr/bin/env bash

# WARNING: DO NOT EDIT!
#
# This file was generated by plugin_template, and is managed by it. Please use
# './plugin-template --github pulp_rpm' to update this file.
#
# For more info visit https://github.com/pulp/plugin_template

# make sure this script runs at the repo root
cd "$(dirname "$(realpath -e "$0")")"/../../..
REPO_ROOT="$PWD"

set -euv

source .github/workflows/scripts/utils.sh

if [[ "$TEST" = "docs" || "$TEST" = "publish" ]]; then
  pip install "mistune<2.0.0"
  pip install -r ../pulpcore/doc_requirements.txt
  pip install -r doc_requirements.txt
fi

pip install -r functest_requirements.txt

cd .ci/ansible/

TAG=ci_build
if [[ "$TEST" == "plugin-from-pypi" ]]; then
  PLUGIN_NAME=pulp_rpm
elif [[ "${RELEASE_WORKFLOW:-false}" == "true" ]]; then
  PLUGIN_NAME=./pulp_rpm/dist/pulp_rpm-$PLUGIN_VERSION-py3-none-any.whl
else
  PLUGIN_NAME=./pulp_rpm
fi
if [[ "${RELEASE_WORKFLOW:-false}" == "true" ]]; then
  # Install the plugin only and use published PyPI packages for the rest
  # Quoting ${TAG} ensures Ansible casts the tag as a string.
  cat >> vars/main.yaml << VARSYAML
image:
  name: pulp
  tag: "${TAG}"
plugins:
  - name: pulpcore
    source: pulpcore~=3.7.8
  - name: pulp_rpm
    source:  "${PLUGIN_NAME}"
services:
  - name: pulp
    image: "pulp:${TAG}"
    volumes:
      - ./settings:/etc/pulp
VARSYAML
else
  cat >> vars/main.yaml << VARSYAML
image:
  name: pulp
  tag: "${TAG}"
plugins:
  - name: pulp_rpm
    source: "${PLUGIN_NAME}"
  - name: pulpcore
    source: ./pulpcore
services:
  - name: pulp
    image: "pulp:${TAG}"
    volumes:
      - ./settings:/etc/pulp
VARSYAML
fi

cat >> vars/main.yaml << VARSYAML
pulp_settings: {"allowed_content_checksums": ["sha1", "sha224", "sha256", "sha384", "sha512"], "allowed_export_paths": ["/tmp"], "allowed_import_paths": ["/tmp"]}
pulp_scheme: http

pulp_container_tag: python36

VARSYAML

if [[ "$TEST" == "pulp" || "$TEST" == "performance" || "$TEST" == "upgrade" || "$TEST" == "azure" || "$TEST" == "s3" || "$TEST" == "plugin-from-pypi" || "$TEST" == "generate-bindings" ]]; then
  sed -i -e '/^services:/a \
  - name: pulp-fixtures\
    image: docker.io/pulp/pulp-fixtures:latest\
    env: {BASE_URL: "http://pulp-fixtures:8080"}' vars/main.yaml
fi

if [ "$TEST" = "s3" ]; then
  export MINIO_ACCESS_KEY=AKIAIT2Z5TDYPX3ARJBA
  export MINIO_SECRET_KEY=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
  sed -i -e '/^services:/a \
  - name: minio\
    image: minio/minio\
    env:\
      MINIO_ACCESS_KEY: "'$MINIO_ACCESS_KEY'"\
      MINIO_SECRET_KEY: "'$MINIO_SECRET_KEY'"\
    command: "server /data"' vars/main.yaml
  sed -i -e '$a s3_test: true\
minio_access_key: "'$MINIO_ACCESS_KEY'"\
minio_secret_key: "'$MINIO_SECRET_KEY'"' vars/main.yaml
fi

ansible-playbook build_container.yaml
ansible-playbook start_container.yaml

if [ "$TEST" = "azure" ]; then
  AZURE_STORAGE_CONNECTION_STRING='DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://ci-azurite:10000/devstoreaccount1;'
  az storage container create --name pulp-test --connection-string $AZURE_STORAGE_CONNECTION_STRING
fi

echo ::group::PIP_LIST
cmd_prefix bash -c "pip3 list && pip3 install pipdeptree && pipdeptree"
echo ::endgroup::
