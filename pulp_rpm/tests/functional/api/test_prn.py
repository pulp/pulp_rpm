import pytest
import requests



# @pytest.fixture(scope="session")
# def pulp_openapi_schema_rpm(pulp_api_v3_url):
#     COMPONENT="rpm"
#     return requests.get(f"{pulp_api_v3_url}docs/api.json?bindings&component={COMPONENT}").json()

@pytest.mark.parallel
def test_prn_schema(pulp_openapi_schema):
    """Test that PRN is a part of every serializer with a pulp_href."""
    failed = []
    for name, schema in pulp_openapi_schema["components"]["schemas"].items():
        if name.endswith("Response"):
            if "pulp_href" in schema["properties"]:
                if "prn" in schema["properties"]:
                    prn_schema = schema["properties"]["prn"]
                    if prn_schema["type"] == "string" and prn_schema["readOnly"]:
                        continue
                failed.append(name)

    assert len(failed) == 0
