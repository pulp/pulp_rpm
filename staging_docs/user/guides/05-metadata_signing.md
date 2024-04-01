# Sign Repository Metadata

The RPM plugin is able to sign repository metadata using a [signing service](site:/pulpcore/docs/admin/guides/sign-metadata/) configured by an administrator.
This enables package managers to verify the authenticity of metadata before installing packages
referenced by that metadata. The metadata signing is enabled for all repositories that have a
signing service associated with them.

## Setup

Let us assume that a signing service is already supplied by an administrator and is queryable via
REST API in an ordinary way. The only thing that needs to be done by a user is to create a new
repository with the associated signing service, like so:

```bash
#!/usr/bin/env bash

# Create RPM repository
if [ $# -eq 0 ]; then
  REPO_NAME="foo"
else
  REPO_NAME="$1"
fi
export REPO_NAME

echo "Fetching the signing service."
SIGNING_SERVICE_HREF=$(pulp signing-service show --name 'sign-metadata' | jq -r '.pulp_href')
export SIGNING_SERVICE_HREF

echo "Creating a new repository named ${REPO_NAME}."
REPO_HREF=$(http POST "$BASE_ADDR"/pulp/api/v3/repositories/rpm/rpm/ name="${REPO_NAME}" \
    metadata_signing_service="${SIGNING_SERVICE_HREF}" \
    | jq -r '.pulp_href')
export REPO_HREF

echo "Inspecting Repository."
pulp rpm repository show --name "${REPO_NAME}"
```

Then, the repository needs to be published and a new distribution needs to be created out of it, as
usually. Follow the instructions provided [in the tutorial](site:/pulp_rpm/docs/user/tutorials/01-create_sync_publish/#create-a-publication) to do so.

The publication will automatically contain a detached ascii-armored signature and a public key.
Both the detached signature and the public key are used by package managers during the process of
verification.

## Installing Packages

When a distribution with signed repodata is created, a user can install packages from a signed
repository. But, at first, it is necessary to set up the configuration for the repository. One may
initialize the configuration by leveraging the utility `dnf config-manager` like shown below.
Afterwards, the user should be able to install the packages by running `dnf install packages`.

```bash
#!/usr/bin/env bash

BASE_URL=$(pulp rpm distribution show --name "${DIST_NAME}" | jq -r '.base_url')
BASE_PATH=$(pulp rpm distribution show --name "${DIST_NAME}" | jq -r '.base_path')
PUBLIC_KEY_URL="${BASE_URL}"/repodata/repomd.xml.key

echo "Setting up a YUM repository."
sudo dnf config-manager --add-repo "${BASE_URL}"
sudo dnf config-manager --save \
    --setopt=*"${BASE_PATH}".gpgcheck=0 \
    --setopt=*"${BASE_PATH}".repo_gpgcheck=1 \
    --setopt=*"${BASE_PATH}".gpgkey="${PUBLIC_KEY_URL}"

sudo dnf install --downloadonly -y walrus
```

!!! note
    Package managers take advantage of signed repositories only when the attribute `repo_gpgcheck`
    is set to 1. Also, bear in mind that the attribute `gpgkey` should be configured as well to
    let the managers know which public key has to be used during the verification.

