# Person 1. Apply only after infra/platform has finished.
# Backend key k8s/terraform.tfstate in the same state bucket and lock table.
# Providers: aws, kubernetes ~> 2.35, helm ~> 2.17, time ~> 0.12, http ~> 3.4.
# Kubernetes and Helm auth via aws_eks_cluster_auth and the platform outputs.
# Remote state data source named platform.
