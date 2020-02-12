import json
import os

location = os.path.dirname(os.path.realpath(__file__))

with open(os.path.join(location, "copy_criteria.json")) as copy_json:
    COPY_CRITERIA_SCHEMA = json.load(copy_json)
