# Platform and profile services — start here

This contribution implements the platform and profile services guide against repository commit
`7b32f494e44c353ade0b9d7675fe763f878548a1` (the uploaded ZIP and GitHub HEAD agreed
when checked). Your two services are **Rider** and **Driver**. Your viva letters
are **a: Terraform**, **d: GitOps**, and **g: S3 + PostgreSQL + DynamoDB**.

## 1. Get the project

Clone the team repository, or update your existing checkout after preserving any
uncommitted work:

```bash
git clone https://github.com/pratham-commits/metered.git
cd metered
git switch main
git pull --ff-only origin main
```

Make sure the platform and profile services changes have been merged into `main`
before deployment; Argo CD tracks that branch. For new changes, use a descriptive
branch such as `platform-services` and merge it through the team's review process.

## 2. First prove your code locally (no AWS charges)

Install Python 3.12 and Docker Desktop; start Docker Desktop. Run inside the repo:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
scripts/check-platform.sh
docker compose up --build -d
```

The check script runs 24 tests plus Python/HCL/YAML syntax checks. SQL is mocked in
those tests; AWS uses Moto. The Driver test makes a real gRPC loopback call.
The Compose stack is the separate live integration check: PostgreSQL, LocalStack,
Kafka, migration, Rider and Driver. The other services remain your teammates' work.

Wait for startup and inspect errors if needed:

```bash
docker compose ps
docker compose logs migrate rider driver
curl -f http://localhost:8001/readyz
curl -f http://localhost:8002/readyz
```

Open http://localhost:8001/docs and http://localhost:8002/docs for interactive API forms.
Create a rider using `POST /riders`:

```json
{"name":"Ved Demo","phone":"9000000001","email":"demo@example.com"}
```

Create a driver using `POST /drivers`:

```json
{"name":"Demo Driver","phone":"9000000002","vehicle_number":"TS09AB1234"}
```

Copy the returned driver `id`. On `POST /drivers/{driver_id}/presence`, enter:

```json
{"status":"ONLINE","lat":17.375,"lng":78.375}
```

Expected: HTTP 200, `zone: z11`, a `partition_id` in `p0..p3`, `status: AVAILABLE`,
and `kafka: true`. If Kafka is still starting and it returns false, inspect the Kafka
logs and retry. A driver must be registered before presence; unknown IDs return 404.

Check the actual data stores:

```bash
docker compose exec postgres psql -U rideshare -d rideshare -c 'SELECT id,name,phone FROM riders;'
docker compose exec localstack awslocal dynamodb scan --table-name rideshare_driver_live
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic ride-events --from-beginning --max-messages 1
```

Stop local services with `docker compose down`. This Compose file has no persistent
PostgreSQL volume; treat its data as disposable demo data.

## 3. Set up your AWS identity

On macOS, install the deployment tools if needed:

```bash
brew install awscli terraform kubectl helm jq
aws configure sso
aws sso login --profile YOUR_PROFILE
export AWS_PROFILE=YOUR_PROFILE
export AWS_REGION=ap-south-1
aws sts get-caller-identity
```

Use your institution's assigned authentication method if it is not SSO. Never put AWS
access keys in the repository or send them in chat. You need permission for the AWS
services listed in the assignment. Terraform must be 1.9 or later.

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
python scripts/configure.py --account-id "$ACCOUNT_ID"
terraform fmt -recursive infra
```

The script replaces only platform and profile service account placeholders, including remote state bucket
names. It does not deploy anything. Fill the three real names and IDs in
`task_division.txt`; placeholders are not a finished submission.

## 4. Create the shared platform

These commands create paid AWS resources. Review each plan. EKS, NAT, RDS and MSK
continue billing while idle. Optional EMR is a separate, later step.

```bash
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap validate
terraform -chdir=infra/bootstrap plan -var="account_id=$ACCOUNT_ID"
terraform -chdir=infra/bootstrap apply -var="account_id=$ACCOUNT_ID"

terraform -chdir=infra/platform init
terraform -chdir=infra/platform validate
terraform -chdir=infra/platform plan
terraform -chdir=infra/platform apply
aws eks update-kubeconfig --region ap-south-1 --name rideshare
kubectl get nodes
```

Keep bootstrap's local state safe, outside git. Subsequent stacks use the encrypted
S3 state bucket. Save provider lock files according to your team's policy; the supplied
skeleton currently ignores them. Confirm the pinned AWS/Helm versions are offered in
your account before apply; no provider downloads or cloud plans were possible during
implementation here.

## 5. Publish images and commit their exact tags

Merge your reviewed source branch to `main` using your team's usual process first;
Argo CD tracks `main`. The source must be committed and your working tree clean before
running `push.sh`. The script builds linux/amd64 images even on Apple Silicon laptops.

```bash
scripts/push.sh rider
scripts/push.sh driver
```

Both print `IMAGE ...:<sha>`. Set the printed tags (usually identical if built from the
same commit):

```bash
python scripts/configure.py --account-id "$ACCOUNT_ID" --rider-tag ACTUAL_RIDER_SHA --driver-tag ACTUAL_DRIVER_SHA
git add deploy/apps/rider/deployment.yaml deploy/apps/driver/deployment.yaml deploy/apps/migrate/job.yaml
git commit -m "Set Rider and Driver images for GitOps"
git push
```

The configure script updates the migration image too. Do not leave `REPLACE_SHA` in
any of those three manifests.

## 6. Install Argo CD and deploy through git

```bash
terraform -chdir=infra/k8s init
terraform -chdir=infra/k8s validate
terraform -chdir=infra/k8s plan
terraform -chdir=infra/k8s apply
kubectl -n argocd get applications
kubectl -n rideshare get pods
```

The repository URL is already set to `https://github.com/pratham-commits/metered.git`.
If the repo is private, Argo CD also needs a read-only repository credential configured
through your team's secret management; a URL alone is insufficient.

The local Helm chart creates the Argo CD Applications after Argo's CRDs exist. This
avoids the guide's first-apply failure from Terraform trying to plan a custom resource
before its CRD exists. Initial `rideshare` sync includes only migration, Rider and
Driver. Person 2/3 placeholders cannot block your demo. Once their code/manifests/images
are ready, remove the `directory.include` line from `deploy/gitops/rideshare-app.yaml`,
commit it and apply `infra/k8s` again (Terraform owns the Application pointer).

Access Argo CD:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
kubectl -n argocd get svc argocd-server
```

Use the reported load-balancer hostname and username `admin`. For local access instead,
run `kubectl -n argocd port-forward svc/argocd-server 8080:443` and open https://localhost:8080.
The initial platform Application has no implemented monitoring resources until Person 2
adds them. Its existence does not prove monitoring is complete.

## 7. Prove your three requirement letters

**a — Terraform:**

```bash
terraform -chdir=infra/platform state list
```

Show the VPC, EKS module, PostgreSQL, two DynamoDB tables, trip bucket, SQS queues,
MSK, ECR and service IAM roles.

**g — data stores:** port-forward the deployed services in separate terminals:

```bash
kubectl -n rideshare port-forward svc/rider 8001:8001
kubectl -n rideshare port-forward svc/driver 8002:8002
```

Repeat local profile/presence creation. In AWS, show the driver item in
`rideshare_driver_live`. Query profiles from the Rider pod, which has private RDS access:

```bash
kubectl -n rideshare exec deploy/rider -- python -c 'from rideshare.db import connection; c=connection(); db=c.__enter__(); print(db.execute("SELECT id,name FROM riders").fetchall()); c.__exit__(None,None,None)'
aws dynamodb scan --table-name rideshare_driver_live --region ap-south-1
terraform -chdir=infra/platform output -raw trip_bucket
```

The trip bucket exists now. The **completion file triggering Lambda** requires Person 3;
do not claim that end-to-end proof until their trip service and Fare ZIP are deployed.

**d — GitOps:** show Rider/Driver Healthy and the synced git revision in Argo CD. Change
`rideshare.io/config-version: "1"` to `"2"` in the Rider pod template, commit and push
to `main`. Show Argo CD syncing and the new ReplicaSet. Do not use `kubectl apply` or
`kubectl set image` for service deployment.

## 8. Hand off to the team

Share these outputs through your team's normal private channel:

```bash
terraform -chdir=infra/platform output rds_endpoint
terraform -chdir=infra/platform output match_queue_url
terraform -chdir=infra/platform output trip_bucket
terraform -chdir=infra/platform output kafka_bootstrap
terraform -chdir=infra/platform output service_role_arns
terraform -chdir=infra/platform output ecr_repositories
```

`database_url` and `demo_token` are sensitive outputs. Share only through an approved
private channel, never commit them. Pods receive them from the Terraform-created Secret.
Tell teammates to use the shared dependency version `kafka-python==2.1.2`; the guide's
`2.0.2` fails to import on Python 3.12. The HTTP/gRPC contracts and frozen resource names
are unchanged. Person 2 can retain their ring implementation if its contract tests pass.

## 9. Optional stacks — wait for Person 3

Only when the Fare ZIP exists at `services/fare/dist/fare.zip`:

```bash
terraform -chdir=infra/lambda init
terraform -chdir=infra/lambda validate
terraform -chdir=infra/lambda plan
terraform -chdir=infra/lambda apply
terraform -chdir=infra/lambda output -raw fare_estimate_url
```

Put that URL in a local `infra/k8s/fare.auto.tfvars` as
`fare_estimate_url = "https://.../estimate"`, apply `infra/k8s`, then bump Ride Request's
pod-template config-version annotation in git to restart it. The tfvars file is ignored.

On the Flink demo day only, after Person 3 uploads the JAR:

```bash
terraform -chdir=infra/emr init
terraform -chdir=infra/emr validate
terraform -chdir=infra/emr plan
terraform -chdir=infra/emr apply
```

This stack downloads the JAR to the cluster before `flink run -t yarn-per-job`, enables
RocksDB/checkpoints, and stores EMR logs in S3. Person 2/3 must wire Flink's CloudWatch log
collection for requirement h. Verify the submitted EMR step succeeds; it has not been
run here. Destroy this stack the same day after your demo.

## 10. Cleanup

After the team has saved its evidence, destroy **only stacks you actually applied**,
in this order: EMR, Lambda, Kubernetes, then platform. Remove application load balancers
and let their controllers finish before removing the EKS cluster. The Argo Application
objects intentionally have no cascading-deletion finalizers; review and delete the
application's cloud-backed Services/Ingresses before cluster teardown. Versioned S3
buckets and nonempty ECR repositories may require explicit cleanup; no script silently
empties them. Keep the state bucket until all dependent infrastructure has been removed.

## What changed from the guide

- Python 3.12-compatible Kafka dependency; Docker build errors no longer swallowed.
- LocalStack credentials, readiness checks, repeatable initialization and local ports.
- Duplicate registrations return 409 even under a unique-constraint race; invalid UUIDs
  and coordinates are rejected before SQL/AWS operations.
- Presence checks the profile and cannot reset an assigned driver. Conditional
  transactions remove the previous partition item when a driver moves.
- Candidate queries read every DynamoDB page; gRPC shuts down cleanly.
- IAM includes the operations actually used, including demand reads by Ride Request.
- Argo Application installation avoids the first-plan CRD dependency; EKS authentication
  refreshes through AWS CLI rather than a token captured before a long apply.
- Initial GitOps sync is scoped to completed services; migration gets the Rider image tag.
- Fare URL is explicit and configurable; EMR downloads its JAR before running Flink.

Validation completed here: **24 tests passed**, generated protobuf imports, real gRPC
loopback, Python compilation, HCL parsing, YAML parsing, shell syntax. **Not validated
here:** Docker builds/Compose startup, real PostgreSQL, Terraform provider validation or
plan, AWS resource creation, live Kafka publication, Helm rendering and Argo CD health.

Reference for the CRD planning issue:
https://developer.hashicorp.com/terraform/tutorials/kubernetes/kubernetes-provider
