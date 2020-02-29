#! /bin/bash
# Script to start a Redis Docker container and run a command.
# Sets the environment variables REDIS_HOST and REDIS_PORT.

cleanup() {
    docker stop "${container}" >/dev/null
}

set -eu

if [ $# -lt 2 ]; then
    echo "Usage: $0 [IMAGE:]TAG COMMAND [...]" >&2
    exit 1
fi

image="${1}"
if [[ "${image}" != *:* ]]; then
    image="redis:${image}"
fi
shift

container="$(docker run --rm -d -p127.0.0.1::6379 --name=redis "${image}")"
trap cleanup EXIT

# Wait for Redis to start
for i in {1..10}; do
    if docker exec "${container}" redis-cli ping >/dev/null 2>&1; then
        break
    fi
    sleep 0.1
done

if ! docker exec "${container}" redis-cli ping >/dev/null 2>&1; then
    echo "Redis failed to start" >&2
    exit 1
fi

hp="$(docker port "${container}" 6379)"
port="${hp##*:}"
echo "Redis container started: id=${container:0:12}, port=${port}" >&2

# Set envvars and execute command
export REDIS_HOST='127.0.0.1'
export REDIS_PORT="${port}"
"${@}"
