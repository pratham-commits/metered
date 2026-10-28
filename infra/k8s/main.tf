# Person 1. Letter d bootstrap. Service Deployments are not applied from here.
#
# Namespaces rideshare and monitoring.
# Secret rideshare-secret in rideshare: DATABASE_URL, DEMO_TOKEN.
# Secret rideshare-secret in monitoring: admin-user=admin, admin-password=demo_token.
# ConfigMap rideshare-config: region, table names, bucket, queue URL, Kafka brokers,
# topics ride-events and demand-results, SSL, HASH_NODES=p0,p1,p2,p3, empty FARE_ESTIMATE_URL,
# in-cluster URLs for rider, driver gRPC, dispatch gRPC, trip, and Prometheus.
# IAM role rideshare-aws-load-balancer-controller from the upstream v2.11.0 policy JSON.
# Helm: aws-load-balancer-controller chart 1.11.0, metrics-server chart 3.12.2,
# argo-cd chart 10.11.6 with an internet-facing NLB.
# Wait 90s, then kubernetes_manifest for deploy/gitops/rideshare-app.yaml and platform-app.yaml.
# Edit those yaml files so repoURL is the real GitHub URL before apply.
