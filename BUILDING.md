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

## Cloud Run release

`infra/gcp/` is the Terraform root for the Cloud Run service (project
`voloirex-lab`, region `europe-west1`, min 0 / max 1 instance, CPU only during
requests). `.github/workflows/release-gcp.yml` runs on a Git tag `v*` only:

1. the same tests as CI;
2. image build and push to `europe-west1-docker.pkg.dev/voloirex-lab/lab/astrochecker`
   with GitHub OIDC as `lab-build`; the digest is captured from the push;
3. `terraform plan` as `lab-plan` with that digest, written to the job summary and
   checked by `scripts/plan_policy.py`, which rejects any destroy and any image
   that is not a digest from the lab registry;
4. `terraform apply` of that exact saved plan as `lab-deploy`.

The published URL is the `public_url` output,
`https://astrochecker-262633132420.europe-west1.run.app/`. The app accepts that
hostname only. Rollback: tag an earlier commit. Digests stay in the registry.
The Windows executable workflow keeps running on the same tag.

Terraform is checked offline with mocks, no credentials needed:

```bash
terraform -chdir=infra/gcp init -backend=false
terraform -chdir=infra/gcp test
```

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
