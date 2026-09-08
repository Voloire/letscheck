"""Reject a saved Terraform plan the Cloud Run release must never apply.

Usage: python scripts/plan_policy.py plan.json

Reads ``terraform show -json`` output. Allowed: create, update, read, no-op of the
Cloud Run service with a digest-pinned image from the lab registry. Rejected: any
destroy or replacement, any tag instead of a digest, any other resource type.
Prints one line per planned action for the job summary.
"""

import re
import sys
from pathlib import Path
import json

IMAGE_PREFIX = "europe-west1-docker.pkg.dev/voloirex-lab/lab/astrochecker@sha256:"
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
ALLOWED_TYPES = {"google_cloud_run_v2_service"}
ALLOWED_ACTIONS = {"create", "update", "read", "no-op"}


class PolicyError(ValueError):
    """The plan violates the release policy."""


def check_plan(plan):
    if not isinstance(plan, dict) or not str(plan.get("format_version", "")).startswith("1."):
        raise PolicyError("Unsupported Terraform plan format")
    lines = []
    for item in plan.get("resource_changes", []):
        address = item.get("address", "?")
        change = item.get("change", {})
        actions = change.get("actions", [])
        if "delete" in actions:
            raise PolicyError(f"destroy or replacement is not allowed: {address}")
        if not actions or any(action not in ALLOWED_ACTIONS for action in actions):
            raise PolicyError(f"unrecognized plan actions {actions}: {address}")
        if item.get("type") not in ALLOWED_TYPES:
            raise PolicyError(f"unexpected resource type in the release plan: {address}")
        if item.get("type") == "google_cloud_run_v2_service" and actions != ["no-op"]:
            after = change.get("after") or {}
            templates = after.get("template") or []
            containers = templates[0].get("containers", []) if templates else []
            if not containers:
                raise PolicyError(f"service without containers: {address}")
            for container in containers:
                image = container.get("image") or ""
                if not image.startswith(IMAGE_PREFIX):
                    reason = "digest" if "@sha256:" not in image else "registry"
                    raise PolicyError(f"image must come from the lab registry with a sha256 {reason}: {image!r}")
                if not DIGEST.fullmatch(image[len(IMAGE_PREFIX):]):
                    raise PolicyError(f"image digest is malformed: {image!r}")
        if actions != ["no-op"]:
            lines.append(f"{'/'.join(actions)}  {address}")
    return lines


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        plan = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        lines = check_plan(plan)
    except (OSError, ValueError) as error:
        print(f"Plan policy FAILED: {error}", file=sys.stderr)
        return 1
    print("\n".join(lines) if lines else "No changes.")
    print("Plan policy OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
