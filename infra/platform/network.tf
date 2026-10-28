# Person 1. Letter a. VPC 10.20.0.0/16 in ap-south-1.
#
# 3 public /24 subnets and 3 private /24 subnets, one per AZ.
# Tag public subnets kubernetes.io/role/elb=1 and kubernetes.io/cluster/rideshare=shared.
# Tag private subnets kubernetes.io/role/internal-elb=1 and the same cluster tag.
# Internet gateway, one NAT gateway in public subnet 0, private route table via that NAT.
# Gateway VPC endpoints for S3 and DynamoDB on the private route table.
