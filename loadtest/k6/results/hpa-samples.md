
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
