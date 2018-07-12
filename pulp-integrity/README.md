# pulp-integrity
A simple Pulp integrity checker

## Requirements and Installation

The tool has to be installed on a working Pulp server.

## Usage

`sudo -u apache pulp-integrity --check size --check dark_content | jq '[.report[].repository] | unique'`


`sudo -u apache pulp-integrity --model rpm --validation '(((broken_rpm_symlinks dark_content) size) checksum)' | jq '[.report[].repository] | unique'`

The tool reports a list of found (published) content issues:

```json
{
  "report": [
  {
    "validator": "dark_content, pulp-integrity 2.16, pulp_integrity.generic:DarkContentValidator" ,
    "unit": "rpm: lemon-0-0-1-noarch-sha256-5fff03684c9e503bed5cfdddb327318ad4e2175073811d9d97fcadc3113fbfec" ,
    "unit_id": "c4c29f0f-fb35-4ffa-af3e-309aad24f695" ,
    "repo_id": "rich-deps" ,
    "error": "The path was not found on the filesystem." ,
    "path": "/var/lib/pulp/content/units/rpm/2b/e42bb9d8d3a0eda1dff939766f4ff5e67244fe0536a1fc8f842c088df7edb4/7adf3b78-acc9-4fed-ac1e-c5855fdb83e9"
  } ,
  {
    "validator": "dark_content, pulp-integrity 2.16, pulp_integrity.generic:DarkContentValidator" ,
    "unit": "rpm: lemon-0-0-1-noarch-sha256-5fff03684c9e503bed5cfdddb327318ad4e2175073811d9d97fcadc3113fbfec" ,
    "unit_id": "c4c29f0f-fb35-4ffa-af3e-309aad24f695" ,
    "repo_id": "rich-deps-copy" ,
    "error": "The path was not found on the filesystem." ,
    "path": "/var/lib/pulp/content/units/rpm/2b/e42bb9d8d3a0eda1dff939766f4ff5e67244fe0536a1fc8f842c088df7edb4/7adf3b78-acc9-4fed-ac1e-c5855fdb83e9"
  } ,
  {
    "validator": "dark_content, pulp-integrity 2.16, pulp_integrity.generic:DarkContentValidator" ,
    "unit": "rpm: lemon-0-0-1-noarch-sha256-5fff03684c9e503bed5cfdddb327318ad4e2175073811d9d97fcadc3113fbfec" ,
    "unit_id": "c4c29f0f-fb35-4ffa-af3e-309aad24f695" ,
    "repo_id": "rich-deps-sync" ,
    "error": "The path was not found on the filesystem." ,
    "path": "/var/lib/pulp/content/units/rpm/2b/e42bb9d8d3a0eda1dff939766f4ff5e67244fe0536a1fc8f842c088df7edb4/7adf3b78-acc9-4fed-ac1e-c5855fdb83e9"
  } ,
  {
    "validator": "broken_rpm_symlinks, pulp-rpm-integrity 2.16, pulp_rpm_integrity.validator:BrokenSymlinksValidator" ,
    "unit": "rpm: lemon-0-0-1-noarch-sha256-5fff03684c9e503bed5cfdddb327318ad4e2175073811d9d97fcadc3113fbfec" ,
    "unit_id": "c4c29f0f-fb35-4ffa-af3e-309aad24f695" ,
    "repo_id": "rich-deps" ,
    "error": "The unit has a missing symlink." ,
    "link": "None"
  } ,
  {
    "validator": "broken_rpm_symlinks, pulp-rpm-integrity 2.16, pulp_rpm_integrity.validator:BrokenSymlinksValidator" ,
    "unit": "rpm: lemon-0-0-1-noarch-sha256-5fff03684c9e503bed5cfdddb327318ad4e2175073811d9d97fcadc3113fbfec" ,
    "unit_id": "c4c29f0f-fb35-4ffa-af3e-309aad24f695" ,
    "repo_id": "rich-deps-sync" ,
    "error": "The unit has a broken symlink." ,
    "link": "/var/lib/pulp/published/yum/https/repos/rich-deps-sync/Packages/l/lemon-0-1.noarch.rpm"
  } ,
  {
    "validator": "broken_rpm_symlinks, pulp-rpm-integrity 2.16, pulp_rpm_integrity.validator:BrokenSymlinksValidator" ,
    "unit": "rpm: tablespoon-sugar-0-1-0-noarch-sha256-5591731a1f07b7f1bd7be3777876f5f43e91611619ec62c41fa1d4a038152cc6" ,
    "unit_id": "9fada6ac-4a6e-45e7-bcb7-c9ff6ffb2a30" ,
    "repo_id": "rich-deps" ,
    "error": "The unit has a broken symlink." ,
    "link": "/var/lib/pulp/published/yum/https/repos/rich-deps/Packages/t/tablespoon-sugar-1-0.noarch.rpm"
  } ,
  {
    "validator": "broken_rpm_symlinks, pulp-rpm-integrity 2.16, pulp_rpm_integrity.validator:BrokenSymlinksValidator" ,
    "unit": "rpm: contireau-0-2-10-noarch-sha256-b7386ccd36a861fe11f5179b2db82085025045ca25f5ac0bb90b302cd5f032aa" ,
    "unit_id": "4b483d15-b269-46e7-b32f-0ba77edd2f1d" ,
    "repo_id": "rich-deps" ,
    "error": "The unit has a broken symlink." ,
    "link": "/var/lib/pulp/published/yum/https/repos/rich-deps/Packages/c/contireau-2-10.noarch.rpm"
  } ,
  {
    "validator": "dark_content, pulp-integrity 2.16, pulp_integrity.generic:DarkContentValidator" ,
    "path": "/var/lib/pulp/content/units/rpm/2b/e42bb9d8d3a0eda1dff939766f4ff5e67244fe0536a1fc8f842c088df7edb4/deadbeef-dead-beefdead" ,
    "error": "The path has no content unit in the database."
  } ,
  {
    "validator": "dark_content, pulp-integrity 2.16, pulp_integrity.generic:DarkContentValidator" ,
    "path": "/var/lib/pulp/content/units/rpm/2b/e42bb9d8d3a0eda1dff939766f4ff5e67244fe0536a1fc8f842c088df7edb4/7adf3b78-acc9-4fed-ac1e-c5855fdb83e9." ,
    "error": "The path has no content unit in the database."
  }
  ]
}
```
