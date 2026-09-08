mock_provider "google" {}

variables {
  image = "europe-west1-docker.pkg.dev/voloirex-lab/lab/astrochecker@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}

run "scale_to_zero_public_service" {
  command = plan
  assert {
    condition = (
      google_cloud_run_v2_service.astrochecker.name == "astrochecker" &&
      google_cloud_run_v2_service.astrochecker.location == "europe-west1" &&
      google_cloud_run_v2_service.astrochecker.ingress == "INGRESS_TRAFFIC_ALL" &&
      google_cloud_run_v2_service.astrochecker.invoker_iam_disabled &&
      google_cloud_run_v2_service.astrochecker.deletion_protection
    )
    error_message = "The service must be public without an allUsers IAM binding and protected against destroy."
  }
  assert {
    condition = (
      google_cloud_run_v2_service.astrochecker.scaling[0].min_instance_count == 0 &&
      google_cloud_run_v2_service.astrochecker.scaling[0].max_instance_count == 1 &&
      google_cloud_run_v2_service.astrochecker.scaling[0].scaling_mode == "AUTOMATIC" &&
      google_cloud_run_v2_service.astrochecker.template[0].scaling[0].min_instance_count == 0 &&
      google_cloud_run_v2_service.astrochecker.template[0].scaling[0].max_instance_count == 1
    )
    error_message = "Always asleep until called: min 0, max 1, automatic scaling, never MANUAL."
  }
  assert {
    condition = (
      google_cloud_run_v2_service.astrochecker.template[0].containers[0].resources[0].cpu_idle &&
      google_cloud_run_v2_service.astrochecker.template[0].containers[0].resources[0].limits["cpu"] == "1" &&
      google_cloud_run_v2_service.astrochecker.template[0].containers[0].resources[0].limits["memory"] == "512Mi" &&
      google_cloud_run_v2_service.astrochecker.template[0].max_instance_request_concurrency == 40 &&
      google_cloud_run_v2_service.astrochecker.template[0].timeout == "60s"
    )
    error_message = "Sizing: 1 vCPU, 512 MiB, CPU only during requests, concurrency 40, timeout 60 s."
  }
  assert {
    condition = (
      google_cloud_run_v2_service.astrochecker.template[0].service_account == "lab-runtime@voloirex-lab.iam.gserviceaccount.com" &&
      google_cloud_run_v2_service.astrochecker.template[0].containers[0].image == var.image &&
      google_cloud_run_v2_service.astrochecker.template[0].containers[0].ports[0].container_port == 8080
    )
    error_message = "Roleless runtime identity, digest image, port 8080."
  }
  assert {
    condition = (
      { for e in google_cloud_run_v2_service.astrochecker.template[0].containers[0].env : e.name => e.value } == {
        ASTROCHECKER_PUBLIC_HOST = "astrochecker-262633132420.europe-west1.run.app"
      }
    )
    error_message = "Cloud mode must be switched on with the deterministic run.app hostname."
  }
  assert {
    condition = (
      google_cloud_run_v2_service.astrochecker.template[0].containers[0].startup_probe[0].http_get[0].path == "/api/status" &&
      google_cloud_run_v2_service.astrochecker.template[0].containers[0].startup_probe[0].http_get[0].port == 8080
    )
    error_message = "Startup probe must use /api/status."
  }
  assert {
    condition     = output.public_url == "https://astrochecker-262633132420.europe-west1.run.app/"
    error_message = "public_url must be the hostname the app accepts."
  }
}

run "rejects_image_without_digest" {
  command = plan
  variables {
    image = "europe-west1-docker.pkg.dev/voloirex-lab/lab/astrochecker:v1.0.0"
  }
  expect_failures = [var.image]
}

run "rejects_image_outside_the_lab_registry" {
  command = plan
  variables {
    image = "docker.io/library/python@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  }
  expect_failures = [var.image]
}
