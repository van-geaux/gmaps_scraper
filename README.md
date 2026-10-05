# Google Maps Query Scraper

This scraper reads plain Google Maps searches from a CSV, stores each run in a
table inside one SQLite database, and automatically exports the run to CSV.

## Quick start

1. Install dependencies:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

2. Prepare a CSV with a required `query` column:

   ```csv
   query
   coffee shops in Bandung
   restaurants in Jakarta
   ```

3. Run with the CSV path supplied on the command line:

   ```bash
   python3 main.py --csvinput queries/dummy_queries.csv
   ```

For the Dockerized Selenium and proxy-gateway workflow:

```bash
docker compose up -d --build
python3 main.py --csvinput queries/dummy_queries.csv
```

Selenium and the authenticated `proxy-gateway` run in Docker on the same Linux
machine as the scraper. The scraper runs directly on the host and connects to
Selenium through `http://localhost:4444`.

The gateway keeps proxy credentials away from Chrome. Chrome connects to the
gateway at `proxy-gateway:3128`, while the gateway forwards traffic through
the authenticated upstream proxy.

The default paths are:

- SQLite database: `output/gmaps_scraper.sqlite`
- CSV export: `output/YYYYMMDD_HHMMSS_<query_file_name>.csv`

Each run creates a table in the SQLite database with the same name as its CSV
export, without the `.csv` extension. The result includes the original query
in `SOURCE_QUERY` and the collection time in `SCRAPED_AT`.

The CSV export runs when the batch completes, is interrupted with Ctrl+C, or
stops because of an unrecoverable error. It contains all rows committed before
the stop.

Google Maps feed loading is retried before a query is reported as empty. The
first attempt waits up to 30 seconds; after a refresh, the retry waits up to
20 seconds. When both attempts fail, the log includes the browser title, URL,
and page-source length for diagnosis.

## Configuration

The CSV path is supplied with the required `--csvinput` argument. The config
file controls the Selenium connection, browser, output locations, and logging.
It can also configure an authenticated upstream proxy for detailed HTTP
requests. Chrome uses the local `proxy-gateway` service in the Docker network,
which avoids Chrome's authenticated-proxy limitation. Address files, address levels, categories,
external databases, and manual export menus are not used.

Enable the proxy in `config.yml` and provide credentials through environment
variables or `.env`:

```yaml
Proxy:
  Enabled: true
  Scheme: http
  Host: ${PROXY_HOST}
  Port: ${PROXY_PORT}
  User: ${PROXY_USER}
  Password: ${PROXY_PASSWORD}
```

Credentials are not logged or sent to Chrome. The `proxy-gateway` service
holds the upstream credentials and forwards Chrome traffic through the
authenticated proxy, while detailed requests use an escaped authenticated
proxy URL directly.

Do not commit `.env`. It must contain `PROXY_HOST`, `PROXY_PORT`,
`PROXY_USER`, and `PROXY_PASSWORD` in the project directory. Docker Compose
uses this same file for the proxy gateway, and the scraper uses it for direct
detailed requests.

## Query CSV rules

- The file must contain a column named `query`.
- Blank query rows are ignored.
- Query text is sent to Google Maps exactly as written, after trimming leading
  and trailing whitespace.
- Additional CSV columns are allowed but ignored.
