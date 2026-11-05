resource "google_compute_network" "rideshare" {
  name                    = "rideshare-vpc"
  auto_create_subnetworks = false
  routing_mode            = "GLOBAL"
}

resource "google_compute_subnetwork" "rideshare" {
  name                     = "rideshare-subnet"
  region                   = var.region
  network                  = google_compute_network.rideshare.id
  ip_cidr_range            = "10.20.0.0/20"
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "rideshare-pods"
    ip_cidr_range = "10.24.0.0/14"
  }

  secondary_ip_range {
    range_name    = "rideshare-services"
    ip_cidr_range = "10.28.0.0/20"
  }
}

resource "google_compute_router" "rideshare" {
  name    = "rideshare-router"
  region  = var.region
  network = google_compute_network.rideshare.id
}

resource "google_compute_router_nat" "rideshare" {
  name                               = "rideshare-nat"
  router                             = google_compute_router.rideshare.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

resource "google_compute_firewall" "internal" {
  name    = "rideshare-allow-internal"
  network = google_compute_network.rideshare.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.20.0.0/16", "10.24.0.0/14", "10.28.0.0/20"]
}

resource "google_compute_firewall" "health_checks" {
  name    = "rideshare-allow-health-checks"
  network = google_compute_network.rideshare.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "8000-9100"]
  }

  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
}

resource "google_compute_firewall" "kafka" {
  name    = "rideshare-allow-kafka"
  network = google_compute_network.rideshare.name

  allow {
    protocol = "tcp"
    ports    = ["9092-9096"]
  }

  source_ranges = ["10.20.0.0/16", "10.24.0.0/14", "10.28.0.0/20"]
}

resource "google_compute_global_address" "psa" {
  name          = "rideshare-psa"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  # Let GCP allocate the range. Do not set address to a CIDR string.
  prefix_length = 16
  network       = google_compute_network.rideshare.id
}

resource "google_service_networking_connection" "psa" {
  network                 = google_compute_network.rideshare.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.psa.name]
}
