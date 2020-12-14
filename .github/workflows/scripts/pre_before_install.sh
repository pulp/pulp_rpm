#!/bin/bash
# Simple check if a test was added and 'coverage.md' was updated with PR.

set -euv

# skip this check for everything but PRs
if [ "$GITHUB_EVENT_NAME" != "pull_request" ]; then
  return 0
fi

COMMIT_BEFORE=$(jq --raw-output .before "$GITHUB_EVENT_PATH")
COMMIT_AFTER=$(jq --raw-output .after "$GITHUB_EVENT_PATH")


RANGE=`echo ${COMMIT_BEFORE}..${COMMIT_AFTER}`
COMMIT_RANGE=`echo ${COMMIT_BEFORE}...${COMMIT_AFTER}`

# check for code changes
if [[ ! `git log --no-merges --pretty='format:' --name-only "$RANGE" | grep -v "pulp_rpm/__init__.py" | grep "pulp_rpm/.*.py" || true` ]]
then
  echo "No code changes detected. Skipping coverage and test check."
  return 0
fi

# check if a test was added
NEEDS_TEST="$(git diff --name-only $COMMIT_RANGE | grep -E 'feature|bugfix' || true)"
CONTAINS_TEST="$(git diff --name-only $COMMIT_RANGE | grep -E 'test_' || true)"

if [[ $(git log --format=medium --no-merges "$RANGE" | grep "\[notest\]" || true) ]]
then
  echo "[notest] is present - skipping the check for the test requirement"
elif [ -n "$NEEDS_TEST" ] && [ -z "$CONTAINS_TEST" ]; then
  echo "Every feature and bugfix should come with a test."
  exit 1
fi

if [[ $(git log --format=medium --no-merges "$RANGE" | grep "\[nocoverage\]" || true) ]]
then
  echo "[nocoverage] is present - skipping this check"
  return 0
fi

coverage_file_name="coverage.md"
coverage_original_file_name="coverage_original.md"
master_version="https://raw.githubusercontent.com/pulp/pulp_rpm/master/${coverage_file_name}"

# get original file from master
curl --silent $master_version -o $coverage_original_file_name

# check if coverage.md was updated and clean
if diff -qs $coverage_file_name $coverage_original_file_name
then
  echo "ERROR: coverage.md file is not updated."
  echo "Please update 'coverage.md' file if you are adding a new feature or updating an existing one."
  rm $coverage_original_file_name
  exit 1
else
  rm $coverage_original_file_name
  return 0
fi
