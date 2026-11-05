resource "random_password" "db" {
  length  = 24
  special = false
}

resource "random_password" "demo" {
  length  = 24
  special = false
}

resource "google_sql_database_instance" "rideshare" {
  name                = "rideshare-pg"
  database_version    = "POSTGRES_16"
  region              = var.region
  deletion_protection = false

  settings {
    tier              = "db-f1-micro"
    edition           = "ENTERPRISE"
    disk_size         = 20
    disk_type         = "PD_SSD"
    disk_autoresize   = false
    availability_type = "ZONAL"

    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = false
    }

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.rideshare.id
      enable_private_path_for_google_cloud_services = true
    }

    user_labels = {
      app = "rideshare"
    }
  }

  depends_on = [google_service_networking_connection.psa]
}

resource "google_sql_database" "rideshare" {
  name     = "rideshare"
  instance = google_sql_database_instance.rideshare.name
}

resource "google_sql_user" "rideshare" {
  name     = "rideshare"
  instance = google_sql_database_instance.rideshare.name
  password = random_password.db.result
}

locals {
  database_url = "postgresql://rideshare:${random_password.db.result}@${google_sql_database_instance.rideshare.private_ip_address}:5432/rideshare"
}

resource "google_secret_manager_secret" "database" {
  secret_id = "rideshare-database"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database" {
  secret = google_secret_manager_secret.database.id
  secret_data = jsonencode({
    username = "rideshare"
    password = random_password.db.result
    host     = google_sql_database_instance.rideshare.private_ip_address
    port     = 5432
    dbname   = "rideshare"
    url      = local.database_url
  })
}

resource "google_secret_manager_secret" "demo" {
  secret_id = "rideshare-demo-token"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "demo" {
  secret      = google_secret_manager_secret.demo.id
  secret_data = random_password.demo.result
}

resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  concurrency_mode            = "PESSIMISTIC"
  app_engine_integration_mode = "DISABLED"
  deletion_policy             = "DELETE"
}

resource "google_firestore_index" "demand_zone_window" {
  project    = var.project_id
  database   = google_firestore_database.default.name
  collection = "rideshare_demand_windows"

  fields {
    field_path = "zone"
    order      = "ASCENDING"
  }

  fields {
    field_path = "window_start"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.default]
}

resource "google_storage_bucket" "trips" {
  name                        = "rideshare-trip-files-${var.project_id}"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age            = 7
      matches_prefix = ["gps/"]
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "functions" {
  name                        = "rideshare-function-source-${var.project_id}"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }
}


resource "google_storage_bucket" "dataproc" {
  name                        = "rideshare-dataproc-${var.project_id}"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle_rule {
    condition {
      age = 14
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_pubsub_topic" "match" {
  name = "rideshare-match-jobs"

  message_retention_duration = "604800s"
}

resource "google_pubsub_topic" "dlq" {
  name = "rideshare-match-jobs-dlq"

  message_retention_duration = "1209600s"
}

resource "google_pubsub_subscription" "match" {
  name  = "rideshare-match-jobs-sub"
  topic = google_pubsub_topic.match.name

  ack_deadline_seconds = 60

  expiration_policy {
    ttl = ""
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }
}

locals {
  pubsub_agent = "service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.dlq.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${local.pubsub_agent}"
}

resource "google_pubsub_subscription_iam_member" "dlq_subscriber" {
  project      = var.project_id
  subscription = google_pubsub_subscription.match.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${local.pubsub_agent}"
}
