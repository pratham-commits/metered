resource "kubernetes_namespace" "rideshare" {
  metadata { name = "rideshare" }
}

resource "kubernetes_namespace" "monitoring" {
  metadata { name = "monitoring" }
}

resource "kubernetes_secret" "rideshare" {
  metadata {
    name      = "rideshare-secret"
    namespace = kubernetes_namespace.rideshare.metadata[0].name
  }
  data = {
    DATABASE_URL = data.terraform_remote_state.platform.outputs.database_url
    DEMO_TOKEN   = data.terraform_remote_state.platform.outputs.demo_token
  }
}

resource "kubernetes_secret" "monitoring" {
  metadata {
    name      = "rideshare-secret"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }
  data = {
    admin-user     = "admin"
    admin-password = data.terraform_remote_state.platform.outputs.demo_token
  }
}

resource "kubernetes_config_map" "rideshare" {
  metadata {
    name      = "rideshare-config"
    namespace = kubernetes_namespace.rideshare.metadata[0].name
  }
  data = {
    AWS_REGION              = "ap-south-1"
    DRIVER_TABLE            = "rideshare_driver_live"
    DEMAND_TABLE            = "rideshare_demand_windows"
    TRIP_BUCKET             = data.terraform_remote_state.platform.outputs.trip_bucket
    MATCH_QUEUE_URL         = data.terraform_remote_state.platform.outputs.match_queue_url
    KAFKA_BOOTSTRAP         = data.terraform_remote_state.platform.outputs.kafka_bootstrap
    KAFKA_TOPIC_EVENTS      = "ride-events"
    KAFKA_TOPIC_RESULTS     = "demand-results"
    KAFKA_SECURITY_PROTOCOL = "SSL"
    HASH_NODES              = "p0,p1,p2,p3"
    FARE_ESTIMATE_URL       = var.fare_estimate_url
    RIDER_URL               = "http://rider.rideshare.svc.cluster.local:8001"
    DRIVER_GRPC             = "driver.rideshare.svc.cluster.local:9002"
    DISPATCH_GRPC           = "dispatch.rideshare.svc.cluster.local:9005"
    TRIP_URL                = "http://trip-tracking.rideshare.svc.cluster.local:8006"
    PROMETHEUS_URL          = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"
  }
}

data "http" "lb_policy" {
  url = "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.11.0/docs/install/iam_policy.json"
}

resource "aws_iam_policy" "lb" {
  name   = "rideshare-aws-load-balancer-controller"
  policy = data.http.lb_policy.response_body
}

resource "aws_iam_role" "lb" {
  name = "rideshare-aws-load-balancer-controller"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Federated = data.terraform_remote_state.platform.outputs.oidc_provider_arn }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${data.terraform_remote_state.platform.outputs.oidc_provider}:sub" = "system:serviceaccount:kube-system:aws-load-balancer-controller"
          "${data.terraform_remote_state.platform.outputs.oidc_provider}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lb" {
  role       = aws_iam_role.lb.name
  policy_arn = aws_iam_policy.lb.arn
}

resource "helm_release" "lb" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  version    = "1.11.0"
  namespace  = "kube-system"
  set {
    name  = "clusterName"
    value = data.terraform_remote_state.platform.outputs.cluster_name
  }
  set {
    name  = "region"
    value = "ap-south-1"
  }
  set {
    name  = "vpcId"
    value = data.terraform_remote_state.platform.outputs.vpc_id
  }
  set {
    name  = "serviceAccount.create"
    value = "true"
  }
  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }
  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.lb.arn
  }
}

resource "helm_release" "metrics" {
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  version    = "3.12.2"
  namespace  = "kube-system"
}

resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = "10.11.6"
  namespace        = "argocd"
  create_namespace = true
  depends_on       = [helm_release.lb]
  values = [yamlencode({
    server = {
      service = {
        type = "LoadBalancer"
        annotations = {
          "service.beta.kubernetes.io/aws-load-balancer-type"            = "external"
          "service.beta.kubernetes.io/aws-load-balancer-nlb-target-type" = "ip"
          "service.beta.kubernetes.io/aws-load-balancer-scheme"          = "internet-facing"
        }
      }
    }
  })]
}

resource "helm_release" "applications" {
  name = "rideshare-applications"
  chart = "${path.module}/charts/applications"
  namespace = "argocd"
  depends_on = [helm_release.argocd]
  values = [yamlencode({
    applications = [for name in ["rideshare", "platform"] : merge(
      yamldecode(file("${path.module}/../../deploy/gitops/${name}-app.yaml")),
      { spec = merge(
        yamldecode(file("${path.module}/../../deploy/gitops/${name}-app.yaml")).spec,
        { source = merge(
          yamldecode(file("${path.module}/../../deploy/gitops/${name}-app.yaml")).spec.source,
          { repoURL = var.github_repo }
        ) }
      ) }
    )]
  })]
}

variable "fare_estimate_url" {
  type = string
  default = ""
}
