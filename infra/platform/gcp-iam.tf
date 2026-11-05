locals {
  workload_accounts = {
    driver           = "rideshare-driver"
    matching         = "rideshare-matching"
    dispatch         = "rideshare-dispatch"
    ride_request     = "rideshare-ride-request"
    rider            = "rideshare-rider"
    fare             = "rideshare-fare"
    trip_tracking    = "rideshare-trip-tracking"
    demand_sink      = "rideshare-demand-sink"
    demand_analytics = "rideshare-demand-analytics"
    eventarc         = "rideshare-eventarc"
    dataproc         = "rideshare-dataproc"
  }

  workload_ksa = {
    driver        = "driver"
    matching      = "matching"
    dispatch      = "dispatch"
    ride_request  = "ride-request"
    rider         = "rider"
    trip_tracking = "trip-tracking"
    demand_sink   = "demand-sink"
  }

  common_roles = [
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudtrace.agent",
  ]

  workload_roles = {
    driver           = concat(local.common_roles, ["roles/datastore.user"])
    matching         = concat(local.common_roles, ["roles/datastore.user", "roles/pubsub.publisher", "roles/pubsub.subscriber"])
    dispatch         = concat(local.common_roles, ["roles/datastore.user", "roles/pubsub.publisher", "roles/pubsub.subscriber"])
    ride_request     = concat(local.common_roles, ["roles/pubsub.publisher"])
    rider            = local.common_roles
    # cloudsql.client + datastore.user also appear in infra/functions; same
    # member/role bindings are idempotent and keep the SA correct before that stack.
    fare             = concat(local.common_roles, ["roles/cloudsql.client", "roles/datastore.user"])
    trip_tracking    = concat(local.common_roles, ["roles/datastore.user", "roles/pubsub.publisher"])
    demand_sink      = concat(local.common_roles, ["roles/datastore.user"])
    demand_analytics = concat(local.common_roles, ["roles/pubsub.publisher", "roles/datastore.user", "roles/dataproc.worker"])
    eventarc         = concat(local.common_roles, ["roles/eventarc.eventReceiver", "roles/pubsub.publisher"])
    dataproc         = concat(local.common_roles, ["roles/dataproc.worker", "roles/pubsub.publisher", "roles/datastore.user"])
  }

  role_bindings = merge([
    for name, roles in local.workload_roles : {
      for role in roles : "${name}:${role}" => {
        name = name
        role = role
      }
    }
  ]...)
}

resource "google_service_account" "workload" {
  for_each = local.workload_accounts

  account_id   = each.value
  display_name = "Ride Sharing ${each.key} workload"
}

resource "google_project_iam_member" "workload" {
  for_each = local.role_bindings

  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.workload[each.value.name].email}"
}

resource "google_service_account_iam_member" "workload_identity" {
  for_each = local.workload_ksa

  service_account_id = google_service_account.workload[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[rideshare/${each.value}]"

  # The workload identity pool is created with the GKE cluster.
  depends_on = [google_container_cluster.rideshare]
}

resource "google_service_account" "gke_node" {
  account_id   = "rideshare-gke-node"
  display_name = "Ride Sharing GKE nodes"
}

resource "google_project_iam_member" "gke_node" {
  for_each = toset([
    "roles/artifactregistry.reader",
    "roles/container.defaultNodeServiceAccount",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
    "roles/stackdriver.resourceMetadata.writer",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.gke_node.email}"
}

resource "google_storage_bucket_iam_member" "trip_tracking_writer" {
  bucket = google_storage_bucket.trips.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.workload["trip_tracking"].email}"
}

resource "google_storage_bucket_iam_member" "fare_reader" {
  bucket = google_storage_bucket.trips.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.workload["fare"].email}"
}

resource "google_storage_bucket_iam_member" "dataproc_staging_admin" {
  bucket = google_storage_bucket.dataproc.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.workload["dataproc"].email}"
}

# Cloud Build / Cloud Functions robot SAs are granted on the function-source
# bucket in infra/functions after google_project_service_identity creates them.
# Binding them here races the first-time API enablement on a new project.

resource "google_secret_manager_secret_iam_member" "ride_request_demo" {
  secret_id = google_secret_manager_secret.demo.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.workload["ride_request"].email}"
}
