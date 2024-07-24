# Post and Delete Content

RPM Content (packages, advisories, modulemds, etc) can be submitted to a Pulp Repository individually.

## Post Content

### Package Example

Package upload requires a valid RPM package.

=== "Upload a Package"

    ```bash
    # Get or create a repository
    pulp rpm repository create --name testrepo
    REPOSITORY=testrepo

    # Get a package
    wget https://fixtures.pulpproject.org/rpm-unsigned/bear-4.1-1.noarch.rpm
    PACKAGE="bear-4.1-1.noarch.rpm"
    
    # Upload package to the repo
    PACKAGE_HREF=$(pulp rpm content -t package upload \
        --file "${PACKAGE}" \
        --repository "${REPOSITORY}" \
        | jq -r '.content_summary.added."rpm.package".href')
    
    # Inspect the package
    pulp show --href "${PACKAGE_HREF}"
    ```

=== "Output"

    ```json
      {
        "pulp_href": "/pulp/api/v3/content/rpm/packages/018e9b3a-78c8-7cce-aa9a-034e92ae2e93/",
        "pulp_created": "2024-04-01T19:54:44.297487Z",
        "pulp_last_updated": "2024-04-01T19:54:44.297497Z",
        "md5": "95281cf165536b930d428e06c9072ecc",
        "sha1": "7a1c48b1ed69992c6ca3f20853f46ec88e8de146",
        "sha224": "2c96cdb234d4ace0f95d0d4dcab5c6dbc009f886ad021fb223768dd1",
        "sha256": "ceb0f0bb58be244393cc565e8ee5ef0ad36884d8ba8eec74542ff47d299a34c1",
        "sha384": "444b2be8b1e91f851acced29c00ccc3984106f3f8429c2c6d79d0166bf3fe0ce82942e761f861b52f9d32b8766ac9b01",
        "sha512": "67434c4e7697908572e65007590317dc7e541dc63be68b330b5fdcddf1127ad525487ee4cca41f218a6810c7a936d5da1847e840f751b5b22f3f1a03f4e25a12",
        "artifact": "/pulp/api/v3/artifacts/018e9b3a-785f-7b12-b7c5-cb966c1efcd0/",
        "name": "bear",
        "epoch": "0",
        "version": "4.1",
        "release": "1",
        "arch": "noarch",
        "pkgId": "ceb0f0bb58be244393cc565e8ee5ef0ad36884d8ba8eec74542ff47d299a34c1",
        "checksum_type": "sha256",
        "summary": "A dummy package of bear",
        "description": "A dummy package of bear",
        "url": "http://tstrachota.fedorapeople.org",
        "changelogs": [],
        "files": [
          [
            "",
            "/tmp/",
            "bear.txt",
            "5938462bfd4a5d750e0851f5b82f3ade"
          ]
        ],
        "requires": [],
        "provides": [
          [
            "bear",
            "EQ",
            "0",
            "4.1",
            "1",
            false
          ]
        ],
        "conflicts": [],
        "obsoletes": [],
        "suggests": [],
        "enhances": [],
        "recommends": [],
        "supplements": [],
        "location_base": "",
        "location_href": "bear-4.1-1.noarch.rpm",
        "rpm_buildhost": "smqe-ws15",
        "rpm_group": "Internet/Applications",
        "rpm_license": "GPLv2",
        "rpm_packager": "",
        "rpm_sourcerpm": "bear-4.1-1.src.rpm",
        "rpm_vendor": "",
        "rpm_header_start": 280,
        "rpm_header_end": 1697,
        "is_modular": false,
        "size_archive": 296,
        "size_installed": 42,
        "size_package": 1846,
        "time_build": 1331831374,
        "time_file": 1712001284
      },
    ```

### Advisory Example

Advisory upload requires a file or an artifact containing advisory information in the JSON format.


=== "Upload an Advisory"

    ```bash
    # Get advisory
    echo '{
        "updated": "2014-09-28 00:00:00",
        "issued": "2014-09-24 00:00:00",
        "id": "RHSA-XXXX:XXXX"
    }' > advisory.json
    ADVISORY="advisory.json"
    
    # Upload advisory
    ADVISORY_HREF=$(pulp rpm content -t advisory \
        upload --file "${ADVISORY}" | jq -r '.pulp_href')
    
    # Inspect advisory
    pulp show --href "${ADVISORY_HREF}"
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/content/rpm/advisories/018e9aec-f864-73a1-9e0b-22fc0288be75/",
      "pulp_created": "2024-04-01T18:30:05.157638Z",
      "pulp_last_updated": "2024-04-01T18:30:05.163938Z",
      "id": "RHSA-XXXX:XXXX",
      "updated_date": "2014-09-28 00:00:01",
      "description": "",
      "issued_date": "2014-09-24 00:00:01",
      "fromstr": "",
      "status": "",
      "title": "",
      "summary": "",
      "version": "",
      "type": "",
      "severity": "",
      "solution": "",
      "release": "",
      "rights": "",
      "pushcount": "",
      "pkglist": [],
      "references": [],
      "reboot_suggested": false
    }
    ```

!!! note

    The previous example doesn't relate the Advisory with a Repository.
    To do so, see [Add Content to Repository](site:pulp_rpm/docs/user/guides/modify#add-content-to-repository).

### Other Contents

Rpm Content types that support individual submission are:
`packages`,
`advisories`,
`modulemds`,
`modulemd_defaults`,
`modulemd_obsoletes`. If CLI supports it, you can use the commands below to check the necessary parameters.

```bash
pulp rpm content -t CONTENT_TYPE upload --help
pulp rpm content -t CONTENT_TYPE create --help
```

!!! warning

    `pulp-cli` may not support all of these yet, but they are available in the REST API 
    (e.g, [modulemd_defaults POST](site:pulp_rpm/restapi/#tag/Content:-Modulemd_Defaults/operation/content_rpm_modulemd_defaults_create)).
    
    You may consider [opening a ticket in pulp-cli](https://github.com/pulp/pulp-cli/issues/new/choose) requesting support.

## Delete Content

Deleting *Content* is not part of the user-facing API as a CRUD operation.
There are several architectural reasons for that, one of which is that multiple *Repository Versions* may rely on the same *Content* unit, and forcing a deletion may lead to a broken state.

If you want to remove *Content*, consider using the [Modify API](site:pulp_rpm/docs/user/guides/modify/#remove-content-from-a-repository) to remove the content *from a Repository*, and not from Pulp itself. The latter should be handled by Admins, who should configure Pulp to handle cleanups safely.

