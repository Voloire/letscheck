"""Policy for the saved Terraform plan applied by the Cloud Run release workflow."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import plan_policy  # noqa: E402

DIGEST = "europe-west1-docker.pkg.dev/voloirex-lab/lab/astrochecker@sha256:" + "a" * 64


def service_change(actions, image):
    return {
        "address": "google_cloud_run_v2_service.astrochecker",
        "type": "google_cloud_run_v2_service",
        "change": {
            "actions": actions,
            "after": {"template": [{"containers": [{"image": image}]}]},
        },
    }


def plan_with(*changes):
    return {"format_version": "1.2", "resource_changes": list(changes)}


def test_create_with_digest_passes_and_is_summarized():
    lines = plan_policy.check_plan(plan_with(service_change(["create"], DIGEST)))
    assert lines == ["create  google_cloud_run_v2_service.astrochecker"]


def test_update_in_place_with_new_digest_passes():
    plan_policy.check_plan(plan_with(service_change(["update"], DIGEST)))


def test_no_op_plan_passes():
    assert plan_policy.check_plan(plan_with(service_change(["no-op"], DIGEST))) == []


def test_delete_is_rejected():
    with pytest.raises(plan_policy.PolicyError, match="destroy"):
        plan_policy.check_plan(plan_with(service_change(["delete", "create"], DIGEST)))


def test_tagged_image_is_rejected():
    tagged = "europe-west1-docker.pkg.dev/voloirex-lab/lab/astrochecker:v1.0.0"
    with pytest.raises(plan_policy.PolicyError, match="digest"):
        plan_policy.check_plan(plan_with(service_change(["create"], tagged)))


def test_image_from_another_registry_is_rejected():
    foreign = "docker.io/library/python@sha256:" + "b" * 64
    with pytest.raises(plan_policy.PolicyError, match="registry"):
        plan_policy.check_plan(plan_with(service_change(["create"], foreign)))


def test_unknown_plan_format_is_rejected():
    with pytest.raises(plan_policy.PolicyError, match="format"):
        plan_policy.check_plan({"format_version": "2.0", "resource_changes": []})


def test_unexpected_resource_type_is_rejected():
    stray = {"address": "google_project_iam_member.x", "type": "google_project_iam_member",
             "change": {"actions": ["create"], "after": {}}}
    with pytest.raises(plan_policy.PolicyError, match="unexpected"):
        plan_policy.check_plan(plan_with(stray))


def test_command_line_exit_codes(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(plan_with(service_change(["create"], DIGEST))))
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(plan_with(service_change(["delete"], DIGEST))))
    script = Path(__file__).resolve().parents[1] / "scripts" / "plan_policy.py"
    ok = subprocess.run([sys.executable, script, good], capture_output=True, text=True)
    assert ok.returncode == 0 and "create  google_cloud_run_v2_service.astrochecker" in ok.stdout
    ko = subprocess.run([sys.executable, script, bad], capture_output=True, text=True)
    assert ko.returncode == 1 and "destroy" in ko.stderr
