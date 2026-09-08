# Building AstroChecker

The supported development path runs the Python source locally. Install runtime dependencies from `requirements.txt`, then start the server with `python run.py`.

To rebuild the bundled catalog offline:

```bash
python tools/build_catalog.py
```

The Windows packaging workflow is kept for release experiments. It creates a single executable with the project toolchain; source execution remains the clearest way to develop and troubleshoot the app.

## Container for Cloud Run

The desktop program binds `127.0.0.1` and keeps the observing site in a local
file. The `Dockerfile` runs the same source in an opt-in cloud mode:

- `--host 0.0.0.0` and the `PORT` environment variable (default 8080) bind the
  container port;
- `ASTROCHECKER_PUBLIC_HOST=<hostname>` enables the stateless mode: requests
  must target that hostname, browser origins must be `https://` on it, the
  server keeps no `site.json` (the browser stores the site in `localStorage`)
  and NINA sequences are returned as XML downloads instead of files in
  `~/Downloads`.

```bash
docker build -t astrochecker .
docker run --rm -p 8080:8080 -e ASTROCHECKER_PUBLIC_HOST=localhost astrochecker
```

Without `ASTROCHECKER_PUBLIC_HOST` the container behaves like the desktop
program and rejects every non-loopback client, which is useless behind a proxy.
Deployment to GCP is described in `docs/superpowers/plans/2026-09-06-gcp-cloud-run.md`.

## Checks from the Linux dev box

`scripts/check.sh` replays the GitHub CI `test` job locally and then builds and
smoke-tests the container image. It runs offline and needs no credentials:

```bash
bash scripts/check.sh              # tests, browser suite, image build, container smoke test
bash scripts/check.sh --no-docker  # tests and browser suite only
```

One-time prerequisites on Ubuntu (WSL included): the repo venv in `.venv` with
`requirements.txt` and `requirements-dev.txt`, Chromium for Playwright
(`python -m playwright install chromium` then `sudo python -m playwright install-deps chromium`),
`node` on PATH, and Docker Engine for the container part. The Windows executable
build stays in GitHub Actions only.
