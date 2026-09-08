# AstroChecker on Cloud Run: one public service, asleep until called.
# Released by .github/workflows/release-gcp.yml on a Git tag; the image digest is
# the only input that changes between releases. Foundation (bucket, registry,
# identities, GitHub OIDC) lives in voloirex-lab/infra/bootstrap.
terraform {
  required_version = ">= 1.9, < 2.0"
  backend "gcs" {
    bucket = "voloirex-lab-262633132420-tfstate"
    prefix = "lab/astrochecker" # inside the lab/ prefix the CI identities may write
  }
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.45.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  # Deterministic Cloud Run URL. The app accepts requests for this hostname only,
  # so it is both the env value and the URL to publish.
  public_host = "${var.name}-${var.project_number}.${var.region}.run.app"
}

resource "google_cloud_run_v2_service" "astrochecker" {
  project              = var.project_id
  location             = var.region
  name                 = var.name
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = true # public without an allUsers IAM binding
  deletion_protection  = true

  scaling {
    min_instance_count = 0
    max_instance_count = 1
    scaling_mode       = "AUTOMATIC"
  }

  template {
    service_account                  = var.runtime_service_account
    max_instance_request_concurrency = 40
    timeout                          = "60s"
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    containers {
      image = var.image
      ports { container_port = 8080 }
      env {
        name  = "ASTROCHECKER_PUBLIC_HOST"
        value = local.public_host
      }
      resources {
        limits            = { cpu = "1", memory = "512Mi" } # astropy + IERS exceed 256 MiB
        cpu_idle          = true                            # billed only while serving requests
        startup_cpu_boost = true                            # shortens the astropy import on cold start
      }
      startup_probe {
        http_get {
          path = "/api/status"
          port = 8080
          # Cloud mode accepts the public hostname only; platform probes do not
          # send it by themselves, so the probe sets it explicitly.
          http_headers {
            name  = "Host"
            value = local.public_host
          }
        }
        initial_delay_seconds = 0
        period_seconds        = 2
        timeout_seconds       = 2
        failure_threshold     = 15
      }
    }
  }
}
