# Red Bucket

Python rate limiting library using Redis for shared state. Implements a token
bucket algorithm inspired by nginx.

## Installation

To install the latest released version:

    pip install redbucket

To install the current development version from the master branch on GitHub:

    pip install -U git+https://github.com/nickgaya/redbucket.git

## Development

This project uses Tox to manage virtual environments for unit tests and other
checks. Unit tests are written using the Pytest framework.

## References

* https://www.nginx.com/blog/rate-limiting-nginx/
* https://en.wikipedia.org/wiki/Token_bucket
