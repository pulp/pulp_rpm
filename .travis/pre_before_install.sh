#!/bin/bash
# Simple check if 'coverage.md' was updated with PR.

set -euv

# skip this check for everything but PRs
if [ "$TRAVIS_PULL_REQUEST" = "false" ]; then
  return 0
fi

# skip if '[nocoverage]' found
if [ "$TRAVIS_COMMIT_RANGE" != "" ]; then
  RANGE=$TRAVIS_COMMIT_RANGE
elif [ "$TRAVIS_COMMIT" != "" ]; then
  RANGE=$TRAVIS_COMMIT
fi

# Travis sends the ranges with 3 dots. Git only wants two.
if [[ "$RANGE" == *...* ]]; then
  RANGE=`echo $TRAVIS_COMMIT_RANGE | sed 's/\.\.\./../'`
else
  RANGE="$RANGE~..$RANGE"
fi

if [[ $(git log --format=medium --no-merges "$RANGE" | grep "\[nocoverage\]") ]]
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
  echo "Please update 'coverage.md' file or use '[nocoverage]' in your commit message."
  rm $coverage_original_file_name
  exit 1
else
  rm $coverage_original_file_name
  return 0
fi
