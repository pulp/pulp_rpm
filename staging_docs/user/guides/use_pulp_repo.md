# Get content from Pulp

When content is published and distributed, one can download packages directly from Pulp or point
client tools to a repo distributed by Pulp.

## Download `foo.rpm` from Pulp

=== "Download a Package"

    ```bash
    #!/usr/bin/env bash
    
    # Download a package
    
    # Specify one package from repository used in 'remote.sh'
    if [ -z "${PKG}" ]; then
      PKG="fox-1.1-2.noarch.rpm"
    fi
    
    SHORT="${PKG:0:1}"
    
    # The distribution will return a url that can be used by http clients
    echo "Setting DISTRIBUTION_BASE_URL, which is used to retrieve content from the content app."
    DISTRIBUTION_BASE_URL=$(pulp rpm distribution show --name "${DIST_NAME}" | jq -r '.base_url')
    export DISTRIBUTION_BASE_URL
    
    # If Pulp was installed without CONTENT_HOST set, it's just the path.
    # And httpie will default to localhost:80
    if [[ "${DISTRIBUTION_BASE_URL:0:1}" = "/" ]]; then
        DISTRIBUTION_BASE_URL="${CONTENT_ADDR}""${DISTRIBUTION_BASE_URL}"
    fi
    
    # Download a package from the distribution
    echo "Download a package from the distribution."
    http -d "$DISTRIBUTION_BASE_URL"Packages/"${SHORT}"/"${PKG}"
    ```

=== "Output"

    ```shell
    HTTP/1.1 200 OK
    Accept-Ranges: bytes
    AppTime: D=417
    Cache-Control: max-age=1800
    Connection: keep-alive
    Content-Length: 2473
    Content-Type: application/x-rpm
    Date: Wed, 27 Nov 2019 14:17:43 GMT
    Etag: "9a9-598026a4cfb06"
    Expires: Wed, 27 Nov 2019 14:47:43 GMT
    Last-Modified: Sat, 23 Nov 2019 12:10:24 GMT
    Server: nginx/1.16.1
    Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
    X-Fedora-AppServer: people02.fedoraproject.org
    X-GitProject: (null)
    
    +-----------------------------------------+
    | NOTE: binary data not shown in terminal |
    +-----------------------------------------+
    ```

## Install a package from Pulp

If available, download the config.repo file from the server at distribution's
base_path and store it in /etc/yum.repos.d:

```
curl http://localhost:24816/pulp/content/foo/config.repo > /etc/yum.repos.d/foo.repo
```

Now use dnf to install a package:

```
sudo dnf install walrus
```

If config.repo file is not served by the distribution, it is necessary to manually set up the
configuration for the repository. One may initialize the configuration by leveraging the utility
`dnf config-manager` like shown below. Afterwards, the user should be able to install the packages
by running dnf install packages.

```bash
BASE_URL=$(pulp rpm distribution show --name "${DIST_NAME}" | jq -r '.base_url')
BASE_PATH=$(pulp rpm distribution show --name "${DIST_NAME}" | jq -r '.base_path')

sudo dnf config-manager --add-repo "${BASE_URL}"
sudo dnf config-manager --save \
    --setopt=*"${BASE_PATH}".gpgcheck=0 \
    --setopt=*"${BASE_PATH}".repo_gpgcheck=0 \

sudo dnf install walrus
```

## List and Install applicable Advisories

Make sure Pulp repo is configured in /etc/yum.repos.d/, then use dnf to work with Advisory content.

List applicable Advisories:

`dnf list-sec`

Install a specific advisory:

`sudo dnf update --advisory XXXX-XXXX:XXXX`
