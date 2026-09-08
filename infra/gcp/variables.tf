variable "project_id" {
  type    = string
  default = "voloirex-lab"
}
variable "project_number" {
  type    = string
  default = "262633132420"
  validation {
    condition     = can(regex("^[0-9]+$", var.project_number))
    error_message = "Use the numeric project number; it is part of the run.app hostname."
  }
}
variable "region" {
  type    = string
  default = "europe-west1"
}
variable "name" {
  type    = string
  default = "astrochecker"
  validation {
    condition     = can(regex("^[a-z]([a-z0-9-]{0,18}[a-z0-9])?$", var.name))
    error_message = "Service names are 1-20 lowercase letters, digits or hyphens."
  }
}
variable "image" {
  type        = string
  description = "Digest-pinned image in the lab registry, produced by the release workflow."
  validation {
    condition     = can(regex("^europe-west1-docker\\.pkg\\.dev/voloirex-lab/lab/astrochecker@sha256:[a-f0-9]{64}$", var.image))
    error_message = "Use the lab registry image europe-west1-docker.pkg.dev/voloirex-lab/lab/astrochecker with a sha256 digest, never a tag."
  }
}
variable "runtime_service_account" {
  type        = string
  default     = "lab-runtime@voloirex-lab.iam.gserviceaccount.com"
  description = "Roleless identity from the bootstrap: AstroChecker calls no GCP API."
}
