from pulp_rpm.app.modulemd import parse_modular
import os

sample_file_data = """
---
document: modulemd
version: 2
data:
  name: kangaroo
  stream: 1.10
  version: 20180730223407
  context: deadbeef
  static_context: true
  arch: noarch
  summary: Kangaroo 0.3 module
  description: >-
    A module for the kangaroo 0.3 package
  license:
    module:
      - MIT
    content:
      - MIT
  profiles:
    default:
      rpms:
        - kangaroo
  artifacts:
    rpms:
      - kangaroo-0:0.3-1.noarch
...
---
document: modulemd
version: 2
data:
  name: kangaroo
  stream: "1.10"
  version: 20180704111719
  context: deadbeef
  static_context: false
  arch: noarch
  summary: Kangaroo 0.2 module
  description: >-
    A module for the kangaroo 0.2 package
  license:
    module:
      - MIT
    content:
      - MIT
  profiles:
    default:
      rpms:
        - kangaroo
  artifacts:
    rpms:
      - kangaroo-0:0.2-1.noarch
...
---
document: modulemd-defaults
version: 1
data:
  module: avocado
  modified: 202002242100
  profiles:
    "5.30": [default]
    "stream": [default]
...
---
document: modulemd-obsoletes
version: 1
data:
  modified: 2022-01-24T08:54Z
  module: perl
  stream: 5.30
  eol_date: 2021-06-01T00:00Z
  message: Module stream perl:5.30 is no longer supported. Please switch to perl:5.32
  obsoleted_by:
    module: perl
    stream: 5.40
...
"""


def test_parse_modular_preserves_literal_unquoted_values_3285(tmp_path):
    """Unquoted yaml numbers with trailing/leading zeros are preserved on specific fields"""

    # write data to test_file
    os.chdir(tmp_path)
    file_name = "modulemd.yaml"
    with open(file_name, "w") as file:
        file.write(sample_file_data)

    all, defaults, obsoletes = parse_modular(file_name)

    # check normal, defaults and obsoletes modulemds
    kangoroo1 = all[0]  # unquoted
    kangoroo2 = all[1]  # quoted
    modulemd_defaults = defaults[0]
    modulemd_obsoletes = obsoletes[0]

    assert kangoroo1["name"] == "kangaroo"
    assert kangoroo1["stream"] == "1.10"  # should not be 1.1
    assert kangoroo1["version"] == "20180730223407"
    assert kangoroo1["context"] == "deadbeef"
    assert kangoroo1["static_context"] is True
    assert kangoroo1["arch"] == "noarch"

    assert kangoroo2["name"] == "kangaroo"
    assert kangoroo2["stream"] == "1.10"
    assert kangoroo2["version"] == "20180704111719"
    assert kangoroo2["context"] == "deadbeef"
    assert kangoroo2["static_context"] is False
    assert kangoroo2["arch"] == "noarch"

    # 'stream' keys which have non-scalar values (e.g. list) are parsed normally.
    # Otherwise, weird results are produced (internal pyyaml objects)
    assert modulemd_defaults["module"] == "avocado"
    assert modulemd_defaults.get("modified") is None  # not present
    assert modulemd_defaults["profiles"]["stream"] == ["default"]
    assert modulemd_defaults["profiles"]["5.30"] == ["default"]

    # parse_modular changes the structure and key names for obsoletes
    assert modulemd_obsoletes["modified"] == "2022-01-24T08:54Z"
    assert modulemd_obsoletes["module_name"] == "perl"
    assert modulemd_obsoletes["module_stream"] == "5.30"
    assert modulemd_obsoletes["eol_date"] == "2021-06-01T00:00Z"
    assert (
        modulemd_obsoletes["message"]
        == "Module stream perl:5.30 is no longer supported. Please switch to perl:5.32"
    )
    assert modulemd_obsoletes["obsoleted_by_module_name"] == "perl"
    assert modulemd_obsoletes["obsoleted_by_module_stream"] == "5.40"
