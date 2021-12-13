#!/usr/bin/env bash
set -e

echo "Setting environment variables for default hostname/port for the API and the Content app"
BASE_ADDR=${BASE_ADDR:-http://localhost:24817}
export BASE_ADDR
CONTENT_ADDR=${CONTENT_ADDR:-http://localhost:24816}
export CONTENT_ADDR

# Necessary for `django-admin`
export DJANGO_SETTINGS_MODULE=pulpcore.app.settings

# Set up a config for pulp-cli
if [ ! -f ${HOME}/.config/pulp/cli.toml ]
then
  pulp config create --username admin --password password --base-url "${BASE_ADDR}" --no-verify-ssl
fi

# Poll a Pulp task until it is finished (needed when using httpie to make requests)
wait_until_task_finished() {
    echo "Polling the task until it has reached a final state."
    local task_url=$1
    while true
    do
        response=$(http "$task_url")
        local response
        state=$(jq -r .state <<< "${response}")
        local state
        jq . <<< "${response}"
        case ${state} in
            failed|canceled)
                echo "Task in final state: ${state}"
                exit 1
                ;;
            completed)
                echo "$task_url complete."
                break
                ;;
            *)
                echo "Still waiting..."
                sleep 1
                ;;
        esac
    done
}
