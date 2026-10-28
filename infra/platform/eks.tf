# Person 1. Letter a and the cluster for letter c.
#
# terraform-aws-modules/eks/aws ~> 20.31. Cluster name rideshare, Kubernetes 1.35.
# Private subnets, public and private API endpoint, IRSA enabled, creator admin access.
# Control plane logs: api, audit, authenticator.
# Addons: coredns, kube-proxy, vpc-cni. EBS CSI addon is a separate aws_eks_addon
# with its own IRSA role rideshare-ebs-csi, so it does not cycle with the module.
# Managed node group default: AL2023, t3.medium, min 2, max 4, desired 2.
# Node role also has AmazonEC2ContainerRegistryReadOnly.
# Node security group: all traffic from itself, TCP 8000-9100 from the VPC CIDR.
# Output oidc_provider and oidc_provider_arn for the k8s stack.
