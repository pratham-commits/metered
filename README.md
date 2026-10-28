# Ride Sharing

Cloud Computing assignment. Eight services on AWS in `ap-south-1`. This repository is the skeleton. Each file contains a comment that says what to implement there. The implementation has not been written yet.

The long build guides are local only and are listed in `.gitignore`:

- `docs/00-overview.md`
- `docs/01-person-1.md`
- `docs/02-person-2.md`
- `docs/03-person-3.md`

## Who owns what

| Person | Write these paths | Defends |
|---|---|---|
| Person 1 | `infra/`, `services/common/` except the ring test, `services/rider/`, `services/driver/`, `deploy/apps/migrate/`, `deploy/apps/rider/`, `deploy/apps/driver/`, `deploy/gitops/`, `scripts/`, `docker-compose.yml` | Terraform, GitOps, the three data stores |
| Person 2 | `services/ride-request/`, `services/matching/`, `services/dispatch/`, `services/common/rideshare/hashring.py`, `services/common/tests/`, `proto/`, `deploy/apps/ride-request/`, `deploy/apps/matching/`, `deploy/apps/dispatch/`, `deploy/platform/`, `loadtest/` | Kubernetes scale, consistent hashing, Prometheus, Grafana, logs, the public UI |
| Person 3 | `services/trip-tracking/`, `services/fare/`, `services/demand-analytics/`, `services/demand-sink/`, `deploy/apps/trip-tracking/`, `deploy/apps/topics/`, `deploy/apps/demand-sink/` | The Fare Lambda, REST/gRPC/SQS on the trace, Flink |

`docs/design.md` and `task_division.txt` are filled in before submission. Person 1 merges the design document.

## Layout

```text
infra/bootstrap     state bucket and lock table
infra/platform      VPC, EKS, RDS, DynamoDB, S3, SQS, MSK, ECR, IAM
infra/k8s           namespace, secrets, config, Argo CD, load balancer controller
infra/lambda        Fare functions and the S3 trigger
infra/emr           Flink cluster, created only for the demo
services/           one directory per service, plus the shared rideshare package
proto/ride/v1       gRPC contracts
deploy/apps         service manifests, synced by Argo CD
deploy/gitops       the two Argo CD Application pointers
deploy/platform     Prometheus, Grafana, Fluent Bit
loadtest/k6         the scale test
scripts/push.sh     build and push one image by git SHA
```

Images are published with `scripts/push.sh`. The printed tag is committed into the deployment manifest. Argo CD rolls the pod. `kubectl apply` is not the deploy path for a service.

## Order

Person 1 applies `infra/bootstrap`, then `infra/platform`, then `infra/k8s`. Person 2 and Person 3 implement against the comments in their directories. `infra/lambda` waits for `services/fare/dist/fare.zip`. `infra/emr` is applied on the demo day and destroyed the same day.
