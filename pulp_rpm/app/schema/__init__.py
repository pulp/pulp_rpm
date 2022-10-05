import json
import os

location = os.path.dirname(os.path.realpath(__file__))

with open(os.path.join(location, "copy_config.json")) as copy_config_json:
    COPY_CONFIG_SCHEMA = json.load(copy_config_json)

with open(os.path.join(location, "modulemd.json")) as modulemd_json:
    MODULEMD_SCHEMA = json.load(modulemd_json)
