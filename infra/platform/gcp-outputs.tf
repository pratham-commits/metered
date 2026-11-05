output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "zone" {
  value = var.zone
}

output "network_id" {
  value = google_compute_network.rideshare.id
}

output "subnetwork_id" {
  value = google_compute_subnetwork.rideshare.id
}

output "cluster_name" {
  value = google_container_cluster.rideshare.name
}

output "cluster_endpoint" {
  value = "https://${google_container_cluster.rideshare.endpoint}"
}

output "cluster_ca_certificate" {
  value = google_container_cluster.rideshare.master_auth[0].cluster_ca_certificate
}

output "gke_node_service_account" {
  value = google_service_account.gke_node.email
}

output "workload_service_accounts" {
  value = { for name, sa in google_service_account.workload : name => sa.email }
}

output "firestore_database" {
  value = google_firestore_database.default.name
}

output "driver_collection" {
  value = "rideshare_driver_live"
}

output "demand_collection" {
  value = "rideshare_demand_windows"
}

output "trip_bucket" {
  value = google_storage_bucket.trips.name
}

output "function_source_bucket" {
  value = google_storage_bucket.functions.name
}

output "dataproc_staging_bucket" {
  value = google_storage_bucket.dataproc.name
}

output "match_topic" {
  value = google_pubsub_topic.match.name
}

output "match_subscription" {
  value = google_pubsub_subscription.match.name
}

output "match_dlq" {
  value = google_pubsub_topic.dlq.name
}

output "artifact_registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.rideshare.repository_id}"
}

output "sql_instance_connection_name" {
  value = google_sql_database_instance.rideshare.connection_name
}

output "sql_private_ip" {
  value = google_sql_database_instance.rideshare.private_ip_address
}

output "database_secret_id" {
  value = google_secret_manager_secret.database.secret_id
}

output "database_url" {
  value     = local.database_url
  sensitive = true
}

output "demo_token_secret_id" {
  value = google_secret_manager_secret.demo.secret_id
}

output "kafka_bootstrap" {
  value = "rideshare-kafka-kafka-bootstrap.rideshare.svc.cluster.local:9094"
}

output "demo_token" {
  value     = random_password.demo.result
  sensitive = true
}
