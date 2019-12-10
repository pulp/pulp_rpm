#!/usr/bin/env bash

# Create RPM distribution for publication
export TASK_URL=$(http POST $BASE_ADDR/pulp/api/v3/distributions/rpm/rpm/ \
    name='baz' base_path='foo' publication=$PUBLICATION_HREF | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
wait_until_task_finished $BASE_ADDR$TASK_URL

# After the task is complete, it gives us a new distribution
echo "Set DISTRIBUTION_HREF from finished task."
export DISTRIBUTION_HREF=$(http $BASE_ADDR$TASK_URL| jq -r '.created_resources | first')

echo "Inspecting Distribution."
http $BASE_ADDR$DISTRIBUTION_HREF