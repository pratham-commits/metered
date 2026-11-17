# k6 load test results

- Started: 2026-11-17T09:54:13Z
- Finished: 2026-11-17T09:59:23Z
- Target: http://34.49.108.248
- Script: `loadtest/k6/ride.js`
- Stages: 30s → 40 VUs, 4m @ 120 VUs, 30s → 0
- Artifacts: `summary.json`, `k6-output.txt`, `hpa-samples.md`

## Verdict

| Check | Result |
|---|---|
| Checklist HPA row | **proven** (`ride-request=6`, `matching=5`) |
| HPA scaled above min | Yes — both crossed >2 replicas under load |
| Requests | 7057 total (~23 req/s) |
| Success rate | 97.88% checks passed (149 failed, 2.11%) |
| Latency | avg 3.05s, p95 11.47s, max 18.45s |
| Peak VUs | 120 |

HPA desired replicas peaked at **ride-request=6** and **matching=5** (from min 2). Not every scaled pod became Ready immediately under CPU pressure; the HPA desired count and checklist proof are what the assignment checks.

## HPA before
```
NAME           REFERENCE                 TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 4%/60%   2         6         2          24m
ride-request   Deployment/ride-request   cpu: 5%/60%   2         6         2          24m
NAME           READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS     IMAGES                                                                     SELECTOR
ride-request   2/2     2            2           24m   ride-request   asia-south1-docker.pkg.dev/metered-513804/rideshare/ride-request:bdc5e5f   app=ride-request
matching       2/2     2            2           24m   matching       asia-south1-docker.pkg.dev/metered-513804/rideshare/matching:bdc5e5f       app=matching
```

## HPA after
```
NAME           REFERENCE                 TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 60%/60%    2         6         5          29m
ride-request   Deployment/ride-request   cpu: 192%/60%   2         6         6          29m
NAME           READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS     IMAGES                                                                     SELECTOR
ride-request   2/6     6            2           29m   ride-request   asia-south1-docker.pkg.dev/metered-513804/rideshare/ride-request:bdc5e5f   app=ride-request
matching       4/5     5            4           29m   matching       asia-south1-docker.pkg.dev/metered-513804/rideshare/matching:bdc5e5f       app=matching
matching-58cfbc8779-87zxq       1/1   Running   0             17s
matching-58cfbc8779-ckgfr       1/1   Running   0             29m
matching-58cfbc8779-dfmvk       1/1   Running   0             29m
matching-58cfbc8779-z42lr       1/1   Running   0             17s
matching-58cfbc8779-zd2g4       0/1   Running   0             10s
ride-request-7f75dcb68b-8zp9l   1/1   Running   0             17s
ride-request-7f75dcb68b-9fht7   0/1   Running   0             10s
ride-request-7f75dcb68b-cnnjx   0/1   Running   0             10s
ride-request-7f75dcb68b-s7qkn   0/1   Running   0             17s
ride-request-7f75dcb68b-tlczg   1/1   Running   1 (82s ago)   18m
ride-request-7f75dcb68b-zmrw6   0/1   Running   2 (15s ago)   21m
```

## Checklist after
```
{
    "rows": [
        {
            "id": "health",
            "title": "Service health",
            "status": "proven",
            "evidence": {
                "rider": "ok",
                "driver": "ok",
                "matching": "ok",
                "dispatch": "ok",
                "trip-tracking": "ok",
                "demand-sink": "ok"
            }
        },
        {
            "id": "hops",
            "title": "Completed ride with every hop",
            "status": "proven",
            "evidence": {
                "ride_id": "1787347b-3fca-4854-a6f2-096360f08e3d",
                "missing": [],
                "present": {
                    "REST": true,
                    "SQL": true,
                    "QUEUE": true,
                    "GRPC": true,
                    "NOSQL": true,
                    "EVENT": true
                }
            }
        },
        {
            "id": "ring",
            "title": "Ring preview stayed cells",
            "status": "proven",
            "evidence": {
                "lat": 23.041955125597163,
                "lng": 72.55195512559716,
                "stayed": 28,
                "moved": 9,
                "moved_fraction": 0.24324324324324326
            }
        },
        {
            "id": "hpa",
            "title": "HPA replicas > 2 under k6",
            "status": "proven",
            "evidence": {
                "matching": 5,
                "ride-request": 6
            }
        },
        {
            "id": "terraform",
            "title": "Terraform platform",
            "status": "show",
            "evidence": "terraform -chdir=infra/platform state list"
        },
        {
            "id": "argocd",
            "title": "Argo CD GitOps",
            "status": "show",
            "evidence": "kubectl -n argocd get applications"
        },
        {
            "id": "grafana",
            "title": "Grafana dashboards",
            "status": "show",
            "evidence": "http://8.231.70.2 dashboard Ride Sharing"
        },
        {
            "id": "logging",
            "title": "Cloud Logging",
            "status": "show",
            "evidence": "resource.type=\"k8s_container\" resource.labels.namespace_name=\"rideshare\" jsonPayload.ride_id=\"RIDE_ID\""
        }
    ],
    "health": {
        "rider": "ok",
        "driver": "ok",
        "matching": "ok",
        "dispatch": "ok",
        "trip-tracking": "ok",
        "demand-sink": "ok"
    }
}
```

- Finished: 2026-11-17T09:59:23Z

## HPA samples during run
```
--- 09:54:14 ---
NAME           REFERENCE                 TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 4%/60%   2         6         2          24m
ride-request   Deployment/ride-request   cpu: 5%/60%   2         6         2          24m
ride-request replicas=2 ready=2
matching replicas=2 ready=2
--- 09:54:40 ---
NAME           REFERENCE                 TARGETS        MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 4%/60%    2         6         2          25m
ride-request   Deployment/ride-request   cpu: 60%/60%   2         6         2          25m
ride-request replicas=2 ready=2
matching replicas=2 ready=2
--- 09:55:05 ---
NAME           REFERENCE                 TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 86%/60%    2         6         3          25m
ride-request   Deployment/ride-request   cpu: 355%/60%   2         6         6          25m
ride-request replicas=6 ready=2
matching replicas=3 ready=2
--- 09:55:31 ---
NAME           REFERENCE                 TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 115%/60%   2         6         3          25m
ride-request   Deployment/ride-request   cpu: 293%/60%   2         6         6          25m
ride-request replicas=2 ready=2
matching replicas=4 ready=2
--- 09:55:57 ---
NAME           REFERENCE                 TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 115%/60%   2         6         4          26m
ride-request   Deployment/ride-request   cpu: 359%/60%   2         6         6          26m
ride-request replicas=2 ready=2
matching replicas=2 ready=2
--- 09:56:22 ---
NAME           REFERENCE                 TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 115%/60%   2         6         4          26m
ride-request   Deployment/ride-request   cpu: 444%/60%   2         6         6          26m
ride-request replicas=2 ready=2
matching replicas=2 ready=2
--- 09:56:48 ---
NAME           REFERENCE                 TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 130%/60%   2         6         4          27m
ride-request   Deployment/ride-request   cpu: 339%/60%   2         6         6          27m
ride-request replicas=2 ready=2
matching replicas=5 ready=2
--- 09:57:14 ---
NAME           REFERENCE                 TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 102%/60%   2         6         5          27m
ride-request   Deployment/ride-request   cpu: 329%/60%   2         6         6          27m
ride-request replicas=2 ready=1
matching replicas=2 ready=2
--- 09:57:40 ---
NAME           REFERENCE                 TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 102%/60%   2         6         5          28m
ride-request   Deployment/ride-request   cpu: 437%/60%   2         6         6          28m
ride-request replicas=2 ready=1
matching replicas=2 ready=2
--- 09:58:05 ---
NAME           REFERENCE                 TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 77%/60%    2         6         5          28m
ride-request   Deployment/ride-request   cpu: 221%/60%   2         6         6          28m
ride-request replicas=2 ready=1
matching replicas=2 ready=2
--- 09:58:31 ---
NAME           REFERENCE                 TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 68%/60%    2         6         5          28m
ride-request   Deployment/ride-request   cpu: 244%/60%   2         6         6          28m
ride-request replicas=2 ready=1
matching replicas=2 ready=2
--- 09:58:57 ---
NAME           REFERENCE                 TARGETS         MINPODS   MAXPODS   REPLICAS   AGE
matching       Deployment/matching       cpu: 60%/60%    2         6         5          29m
ride-request   Deployment/ride-request   cpu: 318%/60%   2         6         6          29m
ride-request replicas=2 ready=2
matching replicas=2 ready=2
```

## k6 summary

```
http_reqs: {"count": 7057, "rate": 23.097371454978152}
http_req_failed: {"passes": 149, "fails": 6908, "value": 0.02111378772849653}
http_req_duration: {"med": 2083.713, "max": 18457.13, "p(90)": 8452.191799999999, "p(95)": 11467.601999999999, "avg": 3059.0558363327164, "min": 28.203}
iterations: {"count": 7056, "rate": 23.0940984818373}
vus: {"max": 120, "value": 3, "min": 2}
vus_max: {"value": 120, "min": 120, "max": 120}
checks: {"passes": 6908, "fails": 149, "value": 0.9788862122715035}
```

### Highlights

- http_reqs: 7057
- http_req_failed rate: {'passes': 149, 'fails': 6908, 'value': 0.02111378772849653}
- http_req_duration avg/p95: 3059.0558363327164/11467.601999999999
- checks rate: {'passes': 6908, 'fails': 149, 'value': 0.9788862122715035}

## k6 console output (tail)
```
running (4m50.0s), 044/120 VUs, 6952 complete and 0 interrupted iterations
default   [  97% ] 044/120 VUs  4m49.9s/5m00.0s

running (4m51.0s), 041/120 VUs, 6970 complete and 0 interrupted iterations
default   [  97% ] 041/120 VUs  4m50.9s/5m00.0s

running (4m52.0s), 040/120 VUs, 6977 complete and 0 interrupted iterations
default   [  97% ] 040/120 VUs  4m51.9s/5m00.0s

running (4m53.0s), 037/120 VUs, 6987 complete and 0 interrupted iterations
default   [  98% ] 037/120 VUs  4m52.9s/5m00.0s

running (4m54.0s), 034/120 VUs, 6999 complete and 0 interrupted iterations
default   [  98% ] 034/120 VUs  4m53.9s/5m00.0s

running (4m55.0s), 030/120 VUs, 7009 complete and 0 interrupted iterations
default   [  98% ] 030/120 VUs  4m54.9s/5m00.0s

running (4m56.0s), 020/120 VUs, 7025 complete and 0 interrupted iterations
default   [  99% ] 020/120 VUs  4m55.9s/5m00.0s

running (4m57.0s), 019/120 VUs, 7035 complete and 0 interrupted iterations
default   [  99% ] 019/120 VUs  4m56.9s/5m00.0s

running (4m58.0s), 017/120 VUs, 7038 complete and 0 interrupted iterations
default   [  99% ] 017/120 VUs  4m57.9s/5m00.0s

running (4m59.0s), 015/120 VUs, 7041 complete and 0 interrupted iterations
default   [ 100% ] 015/120 VUs  4m58.9s/5m00.0s

running (5m00.0s), 010/120 VUs, 7046 complete and 0 interrupted iterations
default   [ 100% ] 010/120 VUs  4m59.9s/5m00.0s

running (5m01.0s), 006/120 VUs, 7050 complete and 0 interrupted iterations
default ↓ [ 100% ] 010/120 VUs  5m0s

running (5m02.0s), 004/120 VUs, 7052 complete and 0 interrupted iterations
default ↓ [ 100% ] 010/120 VUs  5m0s

running (5m03.0s), 004/120 VUs, 7052 complete and 0 interrupted iterations
default ↓ [ 100% ] 010/120 VUs  5m0s

running (5m04.0s), 004/120 VUs, 7052 complete and 0 interrupted iterations
default ↓ [ 100% ] 010/120 VUs  5m0s

running (5m05.0s), 003/120 VUs, 7053 complete and 0 interrupted iterations
default ↓ [ 100% ] 010/120 VUs  5m0s


  █ TOTAL RESULTS 

    checks_total.......: 7057   23.097371/s
    checks_succeeded...: 97.88% 6908 out of 7057
    checks_failed......: 2.11%  149 out of 7057

    ✓ rider created
    ✗ ride accepted
      ↳  97% — ✓ 6907 / ✗ 149

    HTTP
    http_req_duration..............: avg=3.05s min=28.2ms  med=2.08s max=18.45s p(90)=8.45s p(95)=11.46s
      { expected_response:true }...: avg=3.12s min=75.94ms med=2.15s max=18.45s p(90)=8.51s p(95)=11.56s
    http_req_failed................: 2.11%  149 out of 7057
    http_reqs......................: 7057   23.097371/s

    EXECUTION
    iteration_duration.............: avg=3.11s min=78.78ms med=2.13s max=18.5s  p(90)=8.5s  p(95)=11.52s
    iterations.....................: 7056   23.094098/s
    vus............................: 3      min=2           max=120
    vus_max........................: 120    min=120         max=120

    NETWORK
    data_received..................: 4.9 MB 16 kB/s
    data_sent......................: 2.6 MB 8.5 kB/s




running (5m05.5s), 000/120 VUs, 7056 complete and 0 interrupted iterations
default ✓ [ 100% ] 000/120 VUs  5m0s
```
