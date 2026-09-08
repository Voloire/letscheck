# Custom Domain for AstroChecker on Cloud Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve AstroChecker at `https://astrocheck.voloirex.com/` with a Google-managed certificate, at zero extra cost, through the existing tag-driven release.

**Architecture:** A `google_cloud_run_domain_mapping` in `infra/gcp/` maps the hostname to the existing service; Cloudflare holds one DNS-only CNAME to `ghs.googlehosted.com`. The app keeps accepting exactly one hostname (`ASTROCHECKER_PUBLIC_HOST`), so the cutover is two releases: the first creates the mapping and lets Google issue the certificate while the app still answers on the run.app hostname; the second switches the hostname. A `serve_on_domain` variable is the switch and doubles as the rollback lever, because the release policy forbids destroys.

**Tech Stack:** Terraform 1.16.1, provider `hashicorp/google` 7.45.0 (`google_cloud_run_domain_mapping`, Cloud Run v1 API), Cloudflare DNS (manual, two records), Google Search Console for domain verification, Python 3.13 for `scripts/plan_policy.py`.

**Spec:** the evaluation in "Decision record" below (no separate spec; the options were compared in the 2026-09-08 session).

## Global Constraints

- Owner rule: `min_instance_count` stays 0 and `cpu_idle` stays true; never an always-on instance. Unchanged by this plan.
- Owner rule: apply, IAM changes and public exposure need the owner's explicit go. Each Git tag `vX.Y.Z` is an exposure step: never create a tag without the owner saying so.
- Release policy (`scripts/plan_policy.py`): no destroy or replacement, digest-pinned image only, known resource types only. The domain mapping must be admitted explicitly.
- Provider pin `7.45.0`, Terraform `>= 1.9, < 2.0`, region `europe-west1`, project `voloirex-lab` (number `262633132420`).
- Cloudflare records for this hostname stay DNS-only (grey cloud). Proxying breaks Google's certificate issuance and renewal.
- CHANGELOG keeps a single `## Unreleased` section; never version it.
- Local full check: `sg docker -c "bash scripts/check.sh"`; Terraform-only check: `terraform -chdir=infra/gcp init -backend=false && terraform -chdir=infra/gcp test`.
- No Cloudflare Terraform provider, no API token, no Worker in this plan (that is the voloirex-lab blueprint, Option B).

---

## Decision record (evaluation of 2026-09-08)

| | A: Cloud Run domain mapping (chosen) | B: Cloudflare Worker proxy | C: Firebase Hosting rewrite | D: Global external ALB |
|---|---|---|---|---|
| Certificate | Google, automatic | Cloudflare Universal SSL | Google | Google |
| Monthly cost delta | 0 | 0 (Workers free plan) | 0 (Spark plan) | about 18 USD (forwarding rule) |
| App code change | none | CSRF check must trust `X-Forwarded-Host` behind a shared secret | none | none |
| Infra change | +1 resource in letscheck, policy and tests | Cloudflare IDs, API token as GitHub secret, Worker code in voloirex-lab | new product, beta provider, `firebase.json` deploy | LB, NEG, cert, IP |
| Main risk | feature in preview, Google discourages it for production, slight latency | two providers in the release path, code to maintain | second deploy tool | cost |

Chosen: A. B remains the right move if the voloirex.com portfolio with the `/demo` router is built later; both can coexist on different hostnames.

Facts verified on 2026-09-08: `lab-deploy` has `roles/run.admin`, `lab-plan` has `roles/run.viewer` (voloirex-lab `infra/bootstrap/workload-foundation.tf`), enough for domain mappings. `voloirex.com` is already on Cloudflare (voloirex-lab `docs/HANDOFF-WSL.md`). The app rejects any Host other than `ASTROCHECKER_PUBLIC_HOST` (`astrochecker/server.py`, `_public_request`). Cloud Run preserves the mapped hostname in the `Host` header the container sees.

## File structure

- `scripts/plan_policy.py`: admit `google_cloud_run_domain_mapping` with a fixed hostname and route; everything else unchanged.
- `tests/test_plan_policy.py`: fixtures and tests for the mapping.
- `infra/gcp/variables.tf`: `domain`, `serve_on_domain`.
- `infra/gcp/main.tf`: `local.run_host`, `local.public_host` switch, the mapping resource.
- `infra/gcp/outputs.tf`: `domain_url`, `domain_dns_records`.
- `infra/gcp/tests/service.tftest.hcl`: assertions for both switch positions and the mapping.
- `BUILDING.md`, `CHANGELOG.md`: published URL and operator notes.

---

### Task 1: Release policy admits the domain mapping

**Files:**
- Modify: `scripts/plan_policy.py`
- Test: `tests/test_plan_policy.py`

**Interfaces:**
- Produces: constants `DOMAIN = "astrocheck.voloirex.com"` and `SERVICE_NAME = "astrochecker"` in `plan_policy`; `ALLOWED_TYPES` includes `google_cloud_run_domain_mapping`. Task 2 must use exactly these values in Terraform.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_plan_policy.py` after `plan_with`:

```python
def mapping_change(actions, name="astrocheck.voloirex.com", route_name="astrochecker"):
    return {
        "address": "google_cloud_run_domain_mapping.astrochecker",
        "type": "google_cloud_run_domain_mapping",
        "change": {
            "actions": actions,
            "after": {"name": name, "location": "europe-west1",
                      "spec": [{"route_name": route_name, "certificate_mode": "AUTOMATIC"}]},
        },
    }


def test_domain_mapping_for_the_service_passes_and_is_summarized():
    lines = plan_policy.check_plan(plan_with(service_change(["no-op"], DIGEST), mapping_change(["create"])))
    assert lines == ["create  google_cloud_run_domain_mapping.astrochecker"]


def test_domain_mapping_with_another_hostname_is_rejected():
    with pytest.raises(plan_policy.PolicyError, match="hostname"):
        plan_policy.check_plan(plan_with(mapping_change(["create"], name="evil.example.com")))


def test_domain_mapping_to_another_service_is_rejected():
    with pytest.raises(plan_policy.PolicyError, match="route"):
        plan_policy.check_plan(plan_with(mapping_change(["create"], route_name="other")))


def test_domain_mapping_delete_is_rejected():
    with pytest.raises(plan_policy.PolicyError, match="destroy"):
        plan_policy.check_plan(plan_with(mapping_change(["delete"])))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_plan_policy.py -q`
Expected: 3 failures. The first fails with `PolicyError: unexpected resource type`, the hostname and route tests fail because `PolicyError` does not match `hostname`/`route` (the type error is raised first). The delete test already passes.

- [ ] **Step 3: Implement the policy**

In `scripts/plan_policy.py` replace the constants block:

```python
IMAGE_PREFIX = "europe-west1-docker.pkg.dev/voloirex-lab/lab/astrochecker@sha256:"
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
DOMAIN = "astrocheck.voloirex.com"
SERVICE_NAME = "astrochecker"
ALLOWED_TYPES = {"google_cloud_run_v2_service", "google_cloud_run_domain_mapping"}
ALLOWED_ACTIONS = {"create", "update", "read", "no-op"}
```

Inside `check_plan`, after the `google_cloud_run_v2_service` block and before `if actions != ["no-op"]:`, add:

```python
        if item.get("type") == "google_cloud_run_domain_mapping" and actions != ["no-op"]:
            after = change.get("after") or {}
            if after.get("name") != DOMAIN:
                raise PolicyError(f"domain mapping hostname must be {DOMAIN}: {after.get('name')!r}")
            specs = after.get("spec") or []
            route = specs[0].get("route_name") if specs else None
            if route != SERVICE_NAME:
                raise PolicyError(f"domain mapping route must be the {SERVICE_NAME} service: {route!r}")
```

Update the module docstring's "Allowed:" sentence to: `Allowed: create, update, read, no-op of the Cloud Run service with a digest-pinned image from the lab registry, and of the domain mapping astrocheck.voloirex.com to that service.`

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_plan_policy.py -q`
Expected: all pass (15 tests).

- [ ] **Step 5: Commit**

```bash
git checkout -b feat/custom-domain
git add scripts/plan_policy.py tests/test_plan_policy.py
git commit -m "feat: release policy admits the astrocheck.voloirex.com domain mapping"
```

---

### Task 2: Terraform domain mapping with a hostname switch

**Files:**
- Modify: `infra/gcp/variables.tf`
- Modify: `infra/gcp/main.tf:24-28` (locals) and append the mapping resource
- Modify: `infra/gcp/outputs.tf`
- Test: `infra/gcp/tests/service.tftest.hcl`

**Interfaces:**
- Consumes: `DOMAIN` and `SERVICE_NAME` from Task 1 (`astrocheck.voloirex.com`, `astrochecker`).
- Produces: variables `domain` (default `astrocheck.voloirex.com`) and `serve_on_domain` (default `false` in this task, flipped to `true` in Task 5); outputs `public_url`, `domain_url`, `domain_dns_records`.

- [ ] **Step 1: Write the failing Terraform tests**

In `infra/gcp/tests/service.tftest.hcl`, replace the `error_message` of the env assertion with `"Cloud mode must be switched on with the hostname the app is meant to serve."` and append these run blocks at the end of the file:

```hcl
run "domain_mapping_points_at_the_service" {
  command = plan
  assert {
    condition = (
      google_cloud_run_domain_mapping.astrochecker.name == "astrocheck.voloirex.com" &&
      google_cloud_run_domain_mapping.astrochecker.location == "europe-west1" &&
      google_cloud_run_domain_mapping.astrochecker.metadata[0].namespace == "voloirex-lab" &&
      google_cloud_run_domain_mapping.astrochecker.spec[0].route_name == "astrochecker" &&
      google_cloud_run_domain_mapping.astrochecker.spec[0].certificate_mode == "AUTOMATIC"
    )
    error_message = "The mapping must bind astrocheck.voloirex.com to the astrochecker service with a Google-managed certificate."
  }
  assert {
    condition     = output.domain_url == "https://astrocheck.voloirex.com/"
    error_message = "domain_url must be the custom hostname."
  }
}

run "serves_on_domain_when_switched" {
  command = plan
  variables {
    serve_on_domain = true
  }
  assert {
    condition = (
      { for e in google_cloud_run_v2_service.astrochecker.template[0].containers[0].env : e.name => e.value } == {
        ASTROCHECKER_PUBLIC_HOST = "astrocheck.voloirex.com"
      } &&
      { for h in google_cloud_run_v2_service.astrochecker.template[0].containers[0].startup_probe[0].http_get[0].http_headers : h.name => h.value } == {
        Host = "astrocheck.voloirex.com"
      } &&
      output.public_url == "https://astrocheck.voloirex.com/"
    )
    error_message = "With serve_on_domain the env, the probe Host and public_url must all be the custom hostname."
  }
}

run "rejects_domain_outside_voloirex_com" {
  command = plan
  variables {
    domain = "astrochecker.example.com"
  }
  expect_failures = [var.domain]
}
```

- [ ] **Step 2: Run the Terraform tests to verify they fail**

Run: `terraform -chdir=infra/gcp init -backend=false -input=false && terraform -chdir=infra/gcp test`
Expected: FAIL. The new run blocks report `Reference to undeclared resource` / `undeclared input variable`.

- [ ] **Step 3: Add the variables**

Append to `infra/gcp/variables.tf`:

```hcl
variable "domain" {
  type        = string
  default     = "astrocheck.voloirex.com"
  description = "Custom hostname mapped to the service. Cloudflare holds a DNS-only CNAME to ghs.googlehosted.com."
  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]*[a-z0-9])?\\.voloirex\\.com$", var.domain))
    error_message = "The hostname must be a single label under voloirex.com."
  }
}
variable "serve_on_domain" {
  type        = bool
  default     = false
  description = "false: the app answers on the run.app hostname while Google issues the certificate; true: the app answers on var.domain only. Flip back to false to roll back without destroying the mapping."
}
```

- [ ] **Step 4: Switch the locals and add the mapping**

In `infra/gcp/main.tf` replace the `locals` block with:

```hcl
locals {
  # Deterministic Cloud Run URL, always mapped by Cloud Run itself.
  run_host = "${var.name}-${var.project_number}.${var.region}.run.app"
  # The one hostname the app accepts: env value, probe Host header and URL to publish.
  public_host = var.serve_on_domain ? var.domain : local.run_host
}
```

Append at the end of `infra/gcp/main.tf`:

```hcl
# Custom hostname with a Google-managed certificate. Prerequisites outside Terraform:
# the deploy identity is a verified owner of voloirex.com in Search Console, and
# Cloudflare has a DNS-only CNAME for var.domain to ghs.googlehosted.com. Terraform
# waits until the mapping is Ready, which includes the certificate; allow 30 minutes.
resource "google_cloud_run_domain_mapping" "astrochecker" {
  project  = var.project_id
  location = var.region
  name     = var.domain
  metadata {
    namespace = var.project_id
  }
  spec {
    route_name       = google_cloud_run_v2_service.astrochecker.name
    certificate_mode = "AUTOMATIC"
  }
  timeouts {
    create = "30m"
  }
}
```

- [ ] **Step 5: Add the outputs**

Append to `infra/gcp/outputs.tf`:

```hcl
output "domain_url" {
  description = "Custom hostname URL; served by the app only when serve_on_domain is true."
  value       = "https://${var.domain}/"
}
output "domain_dns_records" {
  description = "Records Google expects in DNS for the mapping; compare with Cloudflare after the first apply."
  value       = google_cloud_run_domain_mapping.astrochecker.status[0].resource_records
}
```

- [ ] **Step 6: Format and run the Terraform tests**

Run: `terraform fmt -recursive infra && terraform -chdir=infra/gcp validate && terraform -chdir=infra/gcp test`
Expected: `Success! 6 passed, 0 failed.`

- [ ] **Step 7: Commit**

```bash
git add infra/gcp
git commit -m "feat: map astrocheck.voloirex.com to the Cloud Run service behind a hostname switch"
```

---

### Task 3: Operator documentation

**Files:**
- Modify: `BUILDING.md:48-52`
- Modify: `CHANGELOG.md` (top of `## Unreleased`)

- [ ] **Step 1: Document the two-release cutover in BUILDING.md**

Replace the paragraph starting `The published URL is the` with:

```markdown
The published URL is the `public_url` output. Until `serve_on_domain` is true it is
`https://astrochecker-262633132420.europe-west1.run.app/`; afterwards it is
`https://astrocheck.voloirex.com/`. The app accepts that one hostname only.
Rollback: tag an earlier commit. Digests stay in the registry. Rolling the hostname
back means a release with `serve_on_domain = false`, never a destroy of the mapping:
the release policy rejects destroys.

The custom hostname needs two things outside Terraform, done once by the owner:

1. Google must trust the deploy identity for the domain. In Search Console, verify
   the domain property `voloirex.com` with the TXT record it gives you (added in
   Cloudflare DNS), then under Settings, Users and permissions add
   `lab-deploy@voloirex-lab.iam.gserviceaccount.com` as an Owner. Without this the
   apply fails with "Caller is not authorized to administer the domain".
2. Cloudflare DNS: a CNAME `astrocheck` to `ghs.googlehosted.com`, proxy status
   DNS only (grey cloud), TTL Auto. Proxying it breaks certificate issuance and
   renewal. Check with `dig +short astrocheck.voloirex.com CNAME`.

Certificate status, with operator ADC:
`gcloud beta run domain-mappings describe --domain astrocheck.voloirex.com --region europe-west1`.
The Windows executable workflow keeps running on the same tag.
```

- [ ] **Step 2: Add the CHANGELOG entry**

Insert as the first bullet under `## Unreleased` in `CHANGELOG.md`:

```markdown
- Added the custom hostname `astrocheck.voloirex.com`: a Cloud Run domain mapping
  with a Google-managed certificate, a `serve_on_domain` switch that moves the app's
  accepted hostname in a second release, and the release policy now admits that one
  mapping. DNS stays on Cloudflare, DNS-only.
```

- [ ] **Step 3: Run the full local check and commit**

Run: `sg docker -c "bash scripts/check.sh"`
Expected: ends with `== all checks passed`.

```bash
git add BUILDING.md CHANGELOG.md
git commit -m "docs: custom hostname prerequisites and cutover"
```

---

### Task 4: PR, owner prerequisites, first release (certificate)

**Files:** none changed in the repo by this task.

- [ ] **Step 1: Open the PR and merge after the owner's review**

```bash
git push -u origin feat/custom-domain
gh pr create --title "Custom hostname astrocheck.voloirex.com (mapping, certificate first)" --body "Option A of the 2026-09-08 evaluation. Two-release cutover; this PR keeps the app on run.app. See docs/superpowers/plans/2026-09-08-custom-domain-cloud-run.md."
```

Merge only after CI is green and the owner approves.

- [ ] **Step 2: Owner completes the two prerequisites**

The owner, in their browser and Cloudflare dashboard: Search Console verification of `voloirex.com` plus `lab-deploy@voloirex-lab.iam.gserviceaccount.com` as Owner; Cloudflare CNAME `astrocheck` to `ghs.googlehosted.com`, DNS only.

Verify from WSL:

```bash
dig +short astrocheck.voloirex.com CNAME
```

Expected: `ghs.googlehosted.com.`

- [ ] **Step 3: Owner authorizes and creates the tag**

Only after the owner says "go" for `v0.11.0`:

```bash
git checkout main && git pull
git tag -a v0.11.0 -m "Release v0.11.0" && git push origin v0.11.0
```

- [ ] **Step 4: Verify the release**

Watch `gh run watch` for the Cloud Run release workflow. The apply may take up to 30 minutes while the certificate is issued. Expected job summary: `create  google_cloud_run_domain_mapping.astrochecker` under Plan policy, `Plan policy OK`, Released URL still `https://astrochecker-262633132420.europe-west1.run.app/`.

Then:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://astrochecker-262633132420.europe-west1.run.app/api/status
curl -sS -o /dev/null -w '%{http_code}\n' https://astrocheck.voloirex.com/api/status
curl -sSI https://astrocheck.voloirex.com/ 2>&1 | head -1
```

Expected: `200`, then `403` (valid TLS, the app rejects the hostname on purpose), then a `HTTP/2 403` line with no certificate error. A TLS error instead of 403 means the certificate is not ready: check with the `gcloud beta run domain-mappings describe` command from BUILDING.md and wait.

If the workflow failed at apply with "Caller is not authorized to administer the domain": the Search Console owner step is missing; fix it and re-run the workflow from the same tag (`gh run rerun <id>`).

---

### Task 5: Second release, switch the hostname

**Files:**
- Modify: `infra/gcp/variables.tf` (`serve_on_domain` default)
- Modify: `infra/gcp/tests/service.tftest.hcl`
- Modify: `BUILDING.md`

- [ ] **Step 1: Update the Terraform tests first**

In `service.tftest.hcl`, in run `scale_to_zero_public_service`, change the three expected hostnames from `astrochecker-262633132420.europe-west1.run.app` to `astrocheck.voloirex.com` (env map, probe `Host`, `output.public_url`). Rename run `serves_on_domain_when_switched` to `serves_on_run_app_when_switched_off`, set its `variables { serve_on_domain = false }`, and change its three expected values to `astrochecker-262633132420.europe-west1.run.app` with error message `"With serve_on_domain false the app must fall back to the run.app hostname (rollback path)."`.

Run: `terraform -chdir=infra/gcp test`
Expected: FAIL on both changed run blocks (defaults still `false`).

- [ ] **Step 2: Flip the default**

In `infra/gcp/variables.tf` set `serve_on_domain` `default = true`.

Run: `terraform -chdir=infra/gcp test`
Expected: `Success! 6 passed, 0 failed.`

- [ ] **Step 3: Update BUILDING.md**

Replace `Until \`serve_on_domain\` is true it is ... afterwards it is` sentence with: `The published URL is the \`public_url\` output, \`https://astrocheck.voloirex.com/\`. The app accepts that one hostname only; the run.app URL answers 403.`

- [ ] **Step 4: Commit, PR, merge**

```bash
git checkout -b feat/serve-on-domain
git add infra/gcp BUILDING.md
git commit -m "feat: serve AstroChecker on astrocheck.voloirex.com"
git push -u origin feat/serve-on-domain
gh pr create --title "Serve on astrocheck.voloirex.com" --body "Second half of the cutover: flips serve_on_domain. Requires v0.11.0 applied and the certificate verified."
```

- [ ] **Step 5: Owner authorizes and creates the tag**

Only after the owner says "go" for `v0.11.1`:

```bash
git checkout main && git pull
git tag -a v0.11.1 -m "Release v0.11.1" && git push origin v0.11.1
```

- [ ] **Step 6: Verify and record**

```bash
curl -sS https://astrocheck.voloirex.com/api/status
curl -sS -o /dev/null -w '%{http_code}\n' https://astrochecker-262633132420.europe-west1.run.app/api/status
```

Expected: JSON with `"ready": true`, then `403`. Open `https://astrocheck.voloirex.com/` in a browser and run one check, which exercises the https-origin CSRF path.

Update the memory file `cloud-run-project-state.md`: live URL is `https://astrocheck.voloirex.com/`, run.app answers 403, rollback of the hostname is `serve_on_domain = false`.

---

## Self-review

- Spec coverage: certificate by Google (Task 2 `AUTOMATIC`), DNS-only CNAME (Task 3 docs, Task 4 step 2), Search Console owner (Task 3, Task 4), policy admits the mapping (Task 1), zero cost (no new billable resource), cutover without destroy (Tasks 2, 5), rollback path (`serve_on_domain = false`, tested in Task 5).
- Type consistency: `DOMAIN`/`var.domain` = `astrocheck.voloirex.com`; `SERVICE_NAME`/`var.name`/`route_name` = `astrochecker`; the policy reads `after.spec[0].route_name`, matching the provider's plan JSON shape for `google_cloud_run_domain_mapping`.
- Known gap: the mock-provider tests cannot exercise `status[0].resource_records`; the first real apply is the check (compare `domain_dns_records` output with the Cloudflare record).
