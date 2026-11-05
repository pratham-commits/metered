resource "google_artifact_registry_repository" "rideshare" {
  provider      = google-beta
  location      = var.region
  repository_id = "rideshare"
  description   = "Ride Sharing service images"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-last-10"
    action = "KEEP"

    most_recent_versions {
      keep_count = 10
    }
  }
}
