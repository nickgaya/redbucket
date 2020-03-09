#! /bin/bash
# Script to start a Redis Docker container.
#
# If given a command, starts a Redis container, runs the command with REDIS_URL
# and REDIS_CONTAINER environment variables set, then stops the container.
#
# If run without a command, outputs statements to export the environment
# variables.

cleanup() {
    docker stop "${container}" &>/dev/null
}

abort() {
    for arg in "$@"; do
        echo "$arg"
    done >&2
    exit 1
}

set -eu

USAGE="usage: $0 [-i IMAGE | -t TAG] [-n NAME] [command ...]"

image='redis:alpine'
name='redis'
while getopts ':ht:i:n:' opt; do
    case "$opt" in
        t)  image="redis:${OPTARG}" ;;
        i)  image="${OPTARG}" ;;
        n)  name="${OPTARG}" ;;
        :)  abort "-${OPTARG} requires an argument" "${USAGE}" ;;
        \?) abort "invalid option: -${OPTARG}" "${USAGE}" ;;
        *)  abort "${USAGE}" ;;
    esac
done
shift $((OPTIND - 1))

container="$(docker run --rm -d -p127.0.0.1::6379 --name="${name}" "${image}")"
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

host="$(docker port "${container}" 6379)"
port="${host##*:}"
redis_url="redis://localhost:${port}"
echo "Redis container started: id=${container:0:12}, port=${port}" >&2

if [ $# -eq 0 ]; then
    printf "export REDIS_CONTAINER=%q\n" "${container}"
    printf "export REDIS_URL=%q\n" "${redis_url}"
    trap - EXIT
    exit 0
else
    export REDIS_CONTAINER="${container}"
    export REDIS_URL="${redis_url}"
    "${@}"
fi
