#!/usr/bin/env bash

# Create RPM package from an artifact
echo "Create RPM content from artifact."
export TASK_URL=$(http POST $BASE_ADDR/pulp/api/v3/content/rpm/packages/ \
    artifact=$ARTIFACT_HREF relative_path=$PKG | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
wait_until_task_finished $BASE_ADDR$TASK_URL

# After the task is complete, it gives us a new package (RPM content)
echo "Set PACKAGE_HREF from finished task."
export PACKAGE_HREF=$(http $BASE_ADDR$TASK_URL| jq -r '.created_resources | first')

echo "Inspecting Package."
http $BASE_ADDR$PACKAGE_HREF