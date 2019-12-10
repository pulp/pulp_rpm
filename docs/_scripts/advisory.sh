#!/usr/bin/env bash

# Get advisory
echo '{
    "updated": "2014-09-28 00:00:00",
    "issued": "2014-09-24 00:00:00",
    "id": "RHSA-XXXX:XXXX"
}' > advisory.json
export ADVISORY="advisory.json"

# Upload advisory
echo "Upload advisory in JSON format."
export TASK_URL=$(http --form POST $BASE_ADDR/pulp/api/v3/content/rpm/advisories/ \
    file@./$ADVISORY repository=$REPO_HREF \
    relative_path=$ADVISORY | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
wait_until_task_finished $BASE_ADDR$TASK_URL

# After the task is complete, it gives us a new repository version
echo "Set ADVISORY_HREF from finished task."
export ADVISORY_HREF=$(http $BASE_ADDR$TASK_URL \
    | jq -r '.created_resources | .[] | match(".*advisories.*") | .string')

echo "Inspecting advisory."
http $BASE_ADDR$ADVISORY_HREF