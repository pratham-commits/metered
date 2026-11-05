resource "google_container_cluster" "rideshare" {
  name                = "rideshare"
  location            = var.zone
  network             = google_compute_network.rideshare.id
  subnetwork          = google_compute_subnetwork.rideshare.id
  networking_mode     = "VPC_NATIVE"
  deletion_protection = false

  remove_default_node_pool = true
  initial_node_count       = 1

  release_channel {
    channel = "REGULAR"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = "rideshare-pods"
    services_secondary_range_name = "rideshare-services"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = var.admin_cidr
      display_name = "operator"
    }
  }

  addons_config {
    http_load_balancing {
      disabled = false
    }
    horizontal_pod_autoscaling {
      disabled = false
    }
  }

  logging_config {
    enable_components = [
      "SYSTEM_COMPONENTS",
      "WORKLOADS",
      "APISERVER",
      "CONTROLLER_MANAGER",
      "SCHEDULER",
    ]
  }

  # WORKLOADS is invalid for monitoring_config on modern GKE (removed in 1.24+).
  # Use Managed Prometheus for workload metrics instead.
  monitoring_config {
    enable_components = [
      "SYSTEM_COMPONENTS",
      "APISERVER",
      "CONTROLLER_MANAGER",
      "SCHEDULER",
    ]

    managed_prometheus {
      enabled = true
    }
  }

  depends_on = [google_service_networking_connection.psa]
}

resource "google_container_node_pool" "default" {
  name       = "default"
  cluster    = google_container_cluster.rideshare.id
  location   = var.zone
  node_count = 2

  autoscaling {
    min_node_count = 2
    max_node_count = 4
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type    = "e2-standard-2"
    disk_size_gb    = 50
    disk_type       = "pd-balanced"
    image_type      = "COS_CONTAINERD"
    service_account = google_service_account.gke_node.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = {
      app = "rideshare"
    }

    tags = ["rideshare-node"]
  }
}
