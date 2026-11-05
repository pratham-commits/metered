locals {
  fare_handler = try(file("${path.module}/../../services/fare/handler.py"), "")
  fare_source = (
    can(regex("(?m)^def estimate\\(", local.fare_handler)) &&
    can(regex("(?m)^def finalize\\(", local.fare_handler))
  )
  fare_sa     = local.platform.workload_service_accounts["fare"]
  eventarc_sa = local.platform.workload_service_accounts["eventarc"]

  fare_env = {
    GCP_PROJECT        = var.project_id
    FIRESTORE_DATABASE = "(default)"
    DEMAND_COLLECTION  = local.platform.demand_collection
    TRIP_BUCKET        = local.platform.trip_bucket
    DATABASE_SECRET    = local.platform.database_secret_id
    H3_RESOLUTION      = "8"
    H3_NEIGHBOR_K      = "1"
  }
}

data "archive_file" "fare" {
  count       = local.fare_source ? 1 : 0
  type        = "zip"
  output_path = "${path.module}/.terraform/fare.zip"

  source {
    content  = local.fare_handler
    filename = "main.py"
  }

  source {
    content  = file("${path.module}/../../services/fare/requirements.txt")
    filename = "requirements.txt"
  }

  dynamic "source" {
    for_each = fileset("${path.module}/../../services/common/rideshare", "*.py")
    content {
      content  = file("${path.module}/../../services/common/rideshare/${source.value}")
      filename = "rideshare/${source.value}"
    }
  }
}

resource "google_storage_bucket_object" "fare" {
  count = local.fare_source ? 1 : 0

  name   = "fare/fare.zip"
  bucket = local.platform.function_source_bucket
  source = data.archive_file.fare[0].output_path
}

resource "google_project_service_identity" "cloudbuild" {
  provider = google-beta
  project  = var.project_id
  service  = "cloudbuild.googleapis.com"
}

resource "google_project_service_identity" "cloudfunctions" {
  provider = google-beta
  project  = var.project_id
  service  = "cloudfunctions.googleapis.com"
}

resource "google_storage_bucket_iam_member" "cloudbuild_function_source" {
  bucket = local.platform.function_source_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_project_service_identity.cloudbuild.email}"
}

resource "google_storage_bucket_iam_member" "gcf_source_reader" {
  bucket = local.platform.function_source_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_project_service_identity.cloudfunctions.email}"
}

resource "google_service_account" "build" {
  account_id   = "rideshare-fare-build"
  display_name = "Ride Sharing Fare Cloud Functions build"
}

resource "google_project_iam_member" "build" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/cloudbuild.builds.builder",
    "roles/logging.logWriter",
    "roles/storage.objectViewer",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.build.email}"
}

resource "google_service_account_iam_member" "build_act_as_runtime" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${local.fare_sa}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.build.email}"
}

resource "google_service_account_iam_member" "gcf_agent_act_as_build" {
  service_account_id = google_service_account.build.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:service-${data.google_project.this.number}@gcf-admin-robot.iam.gserviceaccount.com"
}

resource "google_service_account_iam_member" "gcf_agent_act_as_runtime" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${local.fare_sa}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:service-${data.google_project.this.number}@gcf-admin-robot.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "runtime" {
  for_each = toset([
    "roles/cloudsql.client",
    "roles/datastore.user",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${local.fare_sa}"
}

resource "google_secret_manager_secret_iam_member" "runtime_database" {
  secret_id = local.platform.database_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.fare_sa}"
}

resource "google_cloudfunctions2_function" "estimate" {
  count = local.fare_source ? 1 : 0

  name     = "rideshare-fare-estimate"
  location = var.region

  build_config {
    runtime         = "python312"
    entry_point     = "estimate"
    service_account = google_service_account.build.id

    source {
      storage_source {
        bucket     = local.platform.function_source_bucket
        object     = google_storage_bucket_object.fare[0].name
        generation = google_storage_bucket_object.fare[0].generation
      }
    }
  }

  service_config {
    max_instance_count    = 3
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = local.fare_sa
    ingress_settings      = "ALLOW_ALL"
    environment_variables = local.fare_env
  }

  depends_on = [
    google_project_iam_member.build,
    google_project_iam_member.runtime,
    google_service_account_iam_member.build_act_as_runtime,
    google_service_account_iam_member.gcf_agent_act_as_build,
    google_service_account_iam_member.gcf_agent_act_as_runtime,
    google_secret_manager_secret_iam_member.runtime_database,
  ]
}

resource "google_cloudfunctions2_function" "final" {
  count = local.fare_source ? 1 : 0

  name     = "rideshare-fare-final"
  location = var.region

  build_config {
    runtime         = "python312"
    entry_point     = "finalize"
    service_account = google_service_account.build.id

    source {
      storage_source {
        bucket     = local.platform.function_source_bucket
        object     = google_storage_bucket_object.fare[0].name
        generation = google_storage_bucket_object.fare[0].generation
      }
    }
  }

  service_config {
    max_instance_count    = 3
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = local.fare_sa
    ingress_settings      = "ALLOW_INTERNAL_ONLY"
    environment_variables = local.fare_env
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.storage.object.v1.finalized"
    retry_policy          = "RETRY_POLICY_RETRY"
    service_account_email = local.eventarc_sa

    event_filters {
      attribute = "bucket"
      value     = local.platform.trip_bucket
    }
  }

  depends_on = [
    google_project_iam_member.build,
    google_project_iam_member.runtime,
    google_service_account_iam_member.build_act_as_runtime,
    google_service_account_iam_member.gcf_agent_act_as_build,
    google_service_account_iam_member.gcf_agent_act_as_runtime,
    google_secret_manager_secret_iam_member.runtime_database,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "estimate_public" {
  count = local.fare_source ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloudfunctions2_function.estimate[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "final_eventarc" {
  count = local.fare_source ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloudfunctions2_function.final[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${local.eventarc_sa}"
}

output "fare_estimate_url" {
  value = local.fare_source ? "${google_cloudfunctions2_function.estimate[0].service_config[0].uri}/estimate" : ""
}

output "fare_final_name" {
  value = local.fare_source ? google_cloudfunctions2_function.final[0].name : ""
}
