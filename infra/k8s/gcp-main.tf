locals {
  platform = data.terraform_remote_state.platform.outputs
}

resource "kubernetes_namespace" "rideshare" {
  metadata {
    name = "rideshare"
  }
}

resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
  }
}

resource "kubernetes_namespace" "argocd" {
  metadata {
    name = "argocd"
  }
}

resource "kubernetes_secret" "rideshare" {
  metadata {
    name      = "rideshare-secret"
    namespace = kubernetes_namespace.rideshare.metadata[0].name
  }

  data = {
    DATABASE_URL = local.platform.database_url
    DEMO_TOKEN   = local.platform.demo_token
  }
}

resource "kubernetes_secret" "monitoring" {
  metadata {
    name      = "rideshare-secret"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }

  data = {
    admin-user     = "admin"
    admin-password = local.platform.demo_token
  }
}

resource "kubernetes_config_map" "rideshare" {
  metadata {
    name      = "rideshare-config"
    namespace = kubernetes_namespace.rideshare.metadata[0].name
  }

  data = {
    GCP_PROJECT              = local.platform.project_id
    STORAGE_BACKEND          = "gcp"
    FIRESTORE_DATABASE       = "(default)"
    DRIVER_COLLECTION        = local.platform.driver_collection
    DEMAND_COLLECTION        = local.platform.demand_collection
    TRIP_BUCKET              = local.platform.trip_bucket
    MATCH_TOPIC              = local.platform.match_topic
    MATCH_SUBSCRIPTION       = local.platform.match_subscription
    KAFKA_BOOTSTRAP          = local.platform.kafka_bootstrap
    KAFKA_TOPIC_EVENTS       = "ride-events"
    KAFKA_TOPIC_RESULTS      = "demand-results"
    KAFKA_SECURITY_PROTOCOL  = "SSL"
    KAFKA_SSL_CA_FILE        = "/etc/kafka/ca.crt"
    KAFKA_SSL_CHECK_HOSTNAME = "false"
    HASH_NODES               = "p0,p1,p2,p3"
    H3_RESOLUTION            = "8"
    H3_NEIGHBOR_K            = "1"
    FARE_ESTIMATE_URL        = var.fare_estimate_url
    RIDER_URL                = "http://rider.rideshare.svc.cluster.local:8001"
    DRIVER_GRPC              = "driver.rideshare.svc.cluster.local:9002"
    DISPATCH_GRPC            = "dispatch.rideshare.svc.cluster.local:9005"
    TRIP_URL                 = "http://trip-tracking.rideshare.svc.cluster.local:8006"
    PROMETHEUS_URL           = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"
  }
}

resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = "10.11.6"
  namespace        = kubernetes_namespace.argocd.metadata[0].name
  create_namespace = false

  values = [yamlencode({
    server = {
      service = {
        type = "ClusterIP"
      }
    }
  })]
}

resource "helm_release" "applications" {
  name       = "rideshare-applications"
  chart      = "${path.module}/charts/applications"
  namespace  = kubernetes_namespace.argocd.metadata[0].name
  depends_on = [helm_release.argocd]

  values = [yamlencode({
    applications = [for name in ["rideshare", "platform"] : merge(
      yamldecode(file("${path.module}/../../deploy/gitops/${name}-app.yaml")),
      {
        spec = merge(
          yamldecode(file("${path.module}/../../deploy/gitops/${name}-app.yaml")).spec,
          {
            source = merge(
              yamldecode(file("${path.module}/../../deploy/gitops/${name}-app.yaml")).spec.source,
              { repoURL = var.github_repo }
            )
          }
        )
      }
    )]
  })]
}
