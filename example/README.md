Example web server using rate limiting.

## Usage

Set up a virtualenv and install dependencies.

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -U -r requirements.txt -e ..

Run the webserver:

    export REDIS_URL='redis://localhost:6379'
    python3 server.py

You can now make some requests:

    $ curl -w' (%{http_code})\n' 'http://localhost:8080/'
    Hello (200)
    $ curl -w' (%{http_code})\n' 'http://localhost:8080/?user=Alice'
    Hello, Alice (200)

If the rate limit is exceeded, the rate limiter will return a 429 status.

    $ curl -w' (%{http_code})\n' 'http://localhost:8080/?user=Alice'
    Rate limit exceeded (429)

You can tinker with the rate limiting parameters to get a feel for how they
work.
