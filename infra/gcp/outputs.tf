output "public_url" {
  description = "The URL to share. The app rejects other hostnames, including the legacy *.a.run.app alias."
  value       = "https://${local.public_host}/"
}
output "service_uri" {
  description = "URL reported by Cloud Run; informational."
  value       = google_cloud_run_v2_service.astrochecker.uri
}
output "image" { value = var.image }
