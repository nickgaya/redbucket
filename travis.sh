#! /bin/bash

set -ex

if [ -n "${REDIS_TAG}" ]; then
    ./docker_redis.sh -t "${REDIS_TAG}" -- tox -e "${TOXENV}"
else
    tox -e "${TOXENV}"
fi
