resource "google_storage_bucket_iam_member" "trip_reader" {
  bucket = local.platform.trip_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${local.dataproc_sa}"
}

resource "google_storage_bucket_object" "kafka_truststore_init" {
  name   = "flink/init-kafka-truststore.sh"
  bucket = local.platform.dataproc_staging_bucket
  source = "${path.module}/init-kafka-truststore.sh"
}

resource "google_compute_firewall" "dataproc_kafka" {
  name    = "rideshare-allow-dataproc-kafka"
  network = local.platform.network_id

  allow {
    protocol = "tcp"
    ports    = ["9095"]
  }

  source_ranges = ["10.20.0.0/16", "10.24.0.0/14"]
}

resource "google_dataproc_cluster" "flink" {
  name   = "rideshare-flink"
  region = var.region

  cluster_config {
    staging_bucket = local.platform.dataproc_staging_bucket
    temp_bucket    = local.platform.dataproc_staging_bucket

    gce_cluster_config {
      subnetwork             = local.platform.subnetwork_id
      internal_ip_only       = true
      service_account        = local.dataproc_sa
      service_account_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
      tags                   = ["rideshare-flink"]
    }

    master_config {
      num_instances = 1
      machine_type  = "e2-standard-2"

      disk_config {
        boot_disk_type    = "pd-standard"
        boot_disk_size_gb = 50
      }
    }

    worker_config {
      num_instances = 2
      machine_type  = "e2-standard-2"

      disk_config {
        boot_disk_type    = "pd-standard"
        boot_disk_size_gb = 50
      }
    }

    software_config {
      image_version       = "2.2-debian12"
      optional_components = ["FLINK"]
    }

    initialization_action {
      script      = "gs://${local.platform.dataproc_staging_bucket}/${google_storage_bucket_object.kafka_truststore_init.name}"
      timeout_sec = 600
    }
  }
}

output "cluster_name" {
  value = google_dataproc_cluster.flink.name
}

output "staging_bucket" {
  value = local.platform.dataproc_staging_bucket
}

output "service_account" {
  value = local.dataproc_sa
}
