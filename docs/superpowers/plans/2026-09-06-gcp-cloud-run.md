# AstroChecker on GCP Cloud Run Plan

> **For agentic workers:** this is a plan, not an authorization. Nothing below has been executed: no code change, no commit, no `terraform plan`, no `terraform apply`. Every cloud step requires the owner's explicit approval per `~/src/voloirex-lab/AGENTS.md`. Work only from WSL `codex-dev`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run AstroChecker as a Cloud Run service on the existing GCP project `voloirex-lab`, released by GitHub Actions on a Git tag, described entirely in Terraform, reachable at the provider URL (`*.run.app`), for one owner and at most a handful of friends. No console clicks, no over-engineered pipeline, no babysitting: the instance starts when the URL is hit and goes away by itself when nobody uses it.

**Architecture:** One container image (Python 3.12 slim, astropy, bundled SQLite catalog) built by GitHub Actions and pushed by digest to the Artifact Registry repository `lab`. One Cloud Run v2 service, 1 vCPU, 512 MiB, min 0 / max 1 instance, CPU only during requests. The foundation (state bucket, registry, CI identities, GitHub OIDC) stays in `voloirex-lab/infra/bootstrap`; the service itself is a small Terraform root released by digest. The app keeps no personal state on the server: the observing site moves to browser storage and NINA exports become HTTP downloads.

**Tech Stack:** Python 3.12, Docker, Artifact Registry, Cloud Run v2, Terraform 1.16.1 with Google provider 7.45.0, GitHub Actions with OIDC (Workload Identity Federation), GCS backend for state.

**Decision record:** written on 2026-09-06 and 2026-09-07 in the WSL session with Franco. Companion documents: `~/src/voloirex-lab/docs/{SPEC,PLAN,TERRAFORM,OPERATIONS,HANDOFF-WSL}.md`.

---

## Owner requirements (verbatim intent)

- Cloud Run if possible, otherwise a container-free method; containerizing is fine.
- Provider DNS is acceptable; no custom domain needed.
- Everything through Terraform and GitHub Actions: no point-and-click, but no over-engineered pipeline either.
- Users: the owner, at most four friends. Scaling is irrelevant.
- The instance must start when the URL is invoked and stop when unused for about ten minutes. No babysitting: nothing to switch on or off by hand.
- Basic operating-cost estimate.

## Where the work runs

Everything runs inside the WSL Ubuntu distro `codex-dev`: tests, browser suite, image
build, `gh`, `terraform`, `gcloud`. Windows is only the host. `codex-dev` has
`[interop] enabled=false`, so Docker Desktop integration cannot reach it: the container
part needs a native Docker Engine in the distro. `scripts/check.sh` replays the CI test
job and the container smoke test locally; the Windows PyInstaller job stays GitHub-only.
Playwright system libraries were installed in `codex-dev` on 2026-09-07
(`playwright install-deps chromium`); the full suite (249 tests) passes there.

## Current state (verified 2026-09-06)

**AstroChecker (`~/projects/letscheck`, branch `fix/deduplicate-window-copy`)**

- `create_server()` binds `("127.0.0.1", port)` (`astrochecker/server.py`, around line 380).
- The handler rejects any client whose address is not `127.0.0.1` or `::1`, and checks that `Origin` matches a `127.0.0.1`/`localhost` `Host` over `http` (`_local_request`, around line 193).
- The observing site is stored server-side in `~/.astrochecker/site.json` or `%LOCALAPPDATA%\AstroChecker\site.json` (`service.py`, `default_site_path`).
- NINA sequences are written to the server's `~/Downloads` (`nina.py`, `export_legacy_sequence`).
- Runtime deps: `astropy==8.0.1`, `astropy-iers-data`, `numpy==2.5.2`, `tzdata`. Package with catalog: 472 KB. No network calls at runtime (CONTRIBUTING rule).
- CI: `.github/workflows/ci.yml` (pytest plus Playwright, Windows PyInstaller smoke) and `release.yml` (Windows exe on tag `v*`).

**GCP (`voloirex-lab`, project number 262633132420, region `europe-west1`)**

- Billing linked, owner account `voloire@voloirex.com`, ADC configured in `codex-dev`.
- The eight foundation APIs are enabled. Local state `infra/bootstrap/terraform.tfstate` holds only those four `google_project_service` resources. Do not start from an empty state.
- Not yet created: state bucket `voloirex-lab-262633132420-tfstate`, Artifact Registry `lab`, service accounts `lab-plan`/`lab-deploy`/`lab-build`/`lab-runtime`, WIF pool/provider `github`, IAM bindings. The 2026-09-05 plan for them (32 add) is superseded and must be regenerated.
- WIF trust is written for repository ID `1358104512` (`Voloire/voloirex-lab`) only.
- Cloudflare account/zone IDs are empty; the `lab` environment root cannot plan without them. Cloudflare is out of scope for this plan.

## Why Cloud Run with a container

- The Dockerfile is about ten lines; the image digest makes rollback a Git revert, which is the blueprint's rule.
- App Engine standard would cost zero (F1 free tier) but deploys a zip through GCS with an awkward Terraform resource; Cloud Functions cannot host a stdlib HTTP server; Cloud Run source deploy still builds a container, through Cloud Build, without a digest under our control.
- DNS: the `https://astrochecker-<hash>-ew.a.run.app` URL comes from the provider with TLS, at no cost. No custom domain in this plan.

## Start on demand, stop by itself

This is native Cloud Run behavior with `min_instance_count = 0` and `scaling_mode = AUTOMATIC`; nothing to build and nothing to operate.

- First request to the URL starts an instance: cold start 3-5 s (Python plus astropy import), then normal latency.
- When requests stop, Cloud Run keeps the idle instance for a while and then removes it on its own. The idle window is decided by Google and is not configurable: today it is up to about 15 minutes, in practice often less. There is no knob for "exactly 10 minutes", and none is needed.
- Idle time costs nothing: with `cpu_idle = true` CPU and memory are billed only while a request is being served. Whether the instance lingers 10 or 15 minutes does not change the bill.
- No switches: the `enabled=false` / `MANUAL` scaling toggle of the voloirex-lab demo module is not used for AstroChecker. The service is always deployed and always asleep until called.
- Do not set `min_instance_count = 1` and do not set CPU always allocated: both turn the service into an always-on machine (see the cost section).

## Phase 1: application changes (repo letscheck)

Implemented on 2026-09-07 on branch `feat/cloud-run` (not merged). Env name chosen: `ASTROCHECKER_PUBLIC_HOST`; the service flag is `AstroCheckerService(stateless=True)`; tests in `tests/test_cloud_mode.py`. The observing site keeps working on the desktop through `/api/site`; the browser copy is a fallback used when the server has none.

All behind an explicit cloud mode so the desktop program stays identical and the existing 159 tests keep passing.

- [x] **Bind and port.** `create_server(host="127.0.0.1", port=0, service=None)`; `run.py` gains `--host` and reads `PORT` when set. Local default unchanged; container uses `0.0.0.0:8080`.
- [x] **Client check.** On Cloud Run `client_address` is an internal proxy address and `Host` is `*.run.app`. In cloud mode (env `ASTROCHECKER_PUBLIC_HOST=<hostname>`) skip the loopback address check and keep the CSRF check: `Origin` must match `Host` with scheme `https`. Local mode keeps today's logic.
- [x] **Observing site moves to the browser.** Store the site in `localStorage` from `app.js`; the server stops persisting `site.json`. Removes both the ephemeral-state problem (lost on scale to zero) and the privacy problem (home coordinates on a public URL). Largest change of the phase; write tests first.
- [x] **NINA export as HTTP download.** The export endpoint returns the XML with `Content-Disposition: attachment; filename=...xml` instead of writing under `~/Downloads`. Keep `build_legacy_sequence_xml` as is; only the delivery changes.
- [x] **Dockerfile** at repo root: `python:3.12-slim` pinned by digest, `pip install --no-cache-dir -r requirements.txt`, copy `astrochecker/` and `run.py`, non-root user, `EXPOSE 8080`, `CMD ["python", "run.py", "--no-browser", "--host", "0.0.0.0", "--port", "8080"]`. Expected image 250-350 MB (numpy, astropy). Add `.dockerignore` (`.venv`, `.runtime`, `.worktrees`, `tests`, `packaging`, `docs`).
- [x] **Health.** `/api/status` already exists; use it as the startup probe.
- [x] **Tests.** Add tests for host binding, the cloud-mode Origin check, and the NINA download response. Keep the Playwright suite unchanged.

Sizing: 1 vCPU, 512 MiB (astropy plus IERS import exceeds the 256 MiB of the demo module), concurrency 40, timeout 60 s, min 0, max 1, `cpu_idle=true`.

## Phase 2: foundation in voloirex-lab (operator ADC from WSL, once)

This is the pending bootstrap of 2026-09-05 with two additions. Generate a new plan from the current state, present it, apply only with explicit authorization.

- [ ] Remaining foundation resources: state bucket, Artifact Registry `lab`, four service accounts, WIF pool and provider `github`, 16 IAM bindings (the 28 resources left from the 32-add plan).
- [ ] **Extend WIF trust to the letscheck repository.** Add letscheck's numeric repository ID and the exact ref of its release workflow to the provider attribute condition and to the federation bindings of `lab-build`, `lab-plan` and `lab-deploy`. This is a change to the bootstrap code in Git, reviewed like any other.
- [ ] Runtime identity: AstroChecker touches no GCP API, so it runs as the roleless `lab-runtime`. Add no roles.
- [ ] Migrate state to the bucket as described in `TERRAFORM.md` (`backend.tf` from the example, `init -migrate-state`), then verify the remote state is present and versioned.

## Phase 3: pipeline and where the service Terraform lives

Two variants. Variant A is recommended: fewer moving parts, and the release reaches GCP without manual steps.

**Variant A, one repository and one workflow (recommended)**

- [ ] `infra/gcp/` in letscheck: one Terraform root with the Cloud Run v2 service (adapted copy of `voloirex-lab/infra/modules/cloud-run` with parametric memory, always `AUTOMATIC` scaling, and without the `lab`-only image regex), GCS backend on the same bucket with `prefix = "astrochecker"`, variables `project_id`, `region`, `image` (digest required by validation), `runtime_service_account`.
- [ ] `.github/workflows/release-gcp.yml`, trigger `push: tags: ["v*"]` only, `permissions: contents: read, id-token: write`, `concurrency` group so two releases never overlap:
  1. run the test job as in `ci.yml`;
  2. build the image and push it to `europe-west1-docker.pkg.dev/voloirex-lab/lab/astrochecker` with OIDC as `lab-build`; capture the digest from the push output;
  3. `terraform plan -var image=...@sha256:<digest>` as `lab-plan`, plan written to the job summary and checked by a small policy script that rejects any destroy and any image without digest;
  4. `terraform apply` of that exact saved plan as `lab-deploy`.
- [ ] Rollback: tag an earlier commit, or apply with the previous digest (kept in the registry; no automatic cleanup).
- [ ] The existing `release.yml` (Windows exe) keeps its trigger; the two workflows coexist on the same tag.
- [ ] The tag is the opt-in: nothing runs from pushes or pull requests. Only the owner creates tags.

**Variant B, everything in voloirex-lab**

- letscheck only builds and pushes the image (OIDC as `lab-build`) and prints the digest.
- The owner copies the digest into `releases/lab.json` of voloirex-lab, opens a PR, merges, then runs `deploy.yml` twice (`operation=plan`, then `operation=apply`) as documented in `OPERATIONS.md`.
- Closer to the blueprint and with a human plan review before apply, but two repositories and three manual steps per release. The `lab` root also needs the Cloudflare router made optional, since today it fails without Cloudflare IDs.

## Authentication

Phase 1 leaves the URL public with no personal data on the server (see the browser-storage step). Anyone who finds the address can run astronomy computations, nothing else; max 1 instance bounds the bill. If access must be limited to the owner and friends, the next step is IAP on Cloud Run with Google accounts: free and expressible in Terraform, but it needs the organization's OAuth consent and support in provider 7.45.0 must be verified first. Deferred to a later phase.

## Operating cost estimate (one owner, a few friends)

Region `europe-west1`, tier 1 prices, assumed use about twenty sessions per month of ten minutes each.

| Item | Estimated monthly use | Free tier | Estimated cost |
| --- | --- | --- | --- |
| Cloud Run CPU | about 12,000 vCPU-seconds | 180,000 | 0 EUR |
| Cloud Run memory | about 6,000 GiB-seconds | 360,000 | 0 EUR |
| Cloud Run requests | a few thousand | 2 million | 0 EUR |
| Network egress | a few MB (pages and XML) | 1 GiB to North America; elsewhere 0.12 USD/GB | under 0.05 EUR |
| Artifact Registry | 0.5-1.5 GB with four or five retained digests | 0.5 GB | 0-0.10 EUR |
| GCS state bucket | under 1 MB, versioned | effectively free | 0 EUR |
| WIF, IAM, run.app URL and TLS | no charge | | 0 EUR |
| Cloud Build | not used, images are built in GitHub Actions | | 0 EUR |
| **Total** | | | **0-0.20 EUR per month**, under 1 EUR even rounding badly |

What would break the estimate: `min_instance_count=1` (always-on instance, about 45-50 EUR per month) and CPU always allocated. The plan keeps `cpu_idle=true` and min 0. With max 1 and concurrency 40 the theoretical ceiling is the cost of a single instance.

## Order of work and approvals required

1. Owner approves Phase 1 and chooses Variant A or B.
2. Owner reviews the new bootstrap plan in voloirex-lab (with the letscheck trust extension) as `terraform plan` output before any apply.
3. Only then: implement Phase 1 on a feature branch with tests first, open a PR, build the first image, release with the first tag.

Until the owner says go, nothing is executed: no commit, no plan, no apply.
